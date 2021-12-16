import torch
#import clip
#from PIL import Image
import zipfile
from pathlib import Path
import json
import math
from collections import defaultdict
from torch.nn.functional import pad
from transformers import AutoTokenizer, AutoModelForMaskedLM
from tqdm import tqdm
import pickle
from sentence_transformers import SentenceTransformer

device = "cuda" if torch.cuda.is_available() else "cpu"

model = SentenceTransformer('AI-Growth-Lab/PatentSBERTa').to(device=device)

def tokenize_string(string, model):
    tokenized = model.tokenize([string])
    input_ids = tokenized['input_ids']
    if len(input_ids[0]) >= 512:
        words = string.split()
        n_words = len(words)
        if n_words < 2:
            # It's not too rare that we get really long words (e.g. mathematical formulas). In this case we just split
            # them exactly in two along the strings instead of white-spaced words
            n_chars = len(string)
            first_half_string = string[:n_chars//2]
            second_half_string = string[n_chars//2:]
            first_tokenized = tokenize_string(first_half_string, model)
            second_tokenized = tokenize_string(second_half_string, model)
        else:
            first_half = words[:n_words//2]
            second_half = words[n_words//2:]
            first_half_string = ' '.join(first_half)
            second_half_string = ' '.join(second_half)
            first_tokenized = tokenize_string(first_half_string, model)
            second_tokenized = tokenize_string(second_half_string, model)
        concatentated_input_ids = torch.cat([first_tokenized['input_ids'], second_tokenized['input_ids']], dim=-1)
        concatentated_attention = torch.cat([first_tokenized['attention_mask'], second_tokenized['attention_mask']], dim=-1)
        tokenized = {'input_ids': concatentated_input_ids, 'attention_mask': concatentated_attention}
    return tokenized


def encode_text(text, model, device=device, batch_size=16, window_length=512):
    #step_size = int(window_length/2)
    step_size = window_length
    with torch.no_grad():
        tokenization_results = tokenize_string(text, model)
        tokenized_text = tokenization_results['input_ids'][0]
        attention_mask = tokenization_results['attention_mask'][0]
        n_tokens = len(tokenized_text)
        if n_tokens < window_length:
            tokenized_text = pad(tokenized_text, (0, window_length-n_tokens))
            attention_mask = pad(attention_mask, (0, window_length-n_tokens))
            n_tokens = len(tokenized_text)
        padded_length = math.ceil((len(tokenized_text) - window_length)/(step_size))*step_size + window_length
        tokenized_text = pad(tokenized_text, (0, padded_length-n_tokens))
        attention_mask = pad(attention_mask, (0, padded_length-n_tokens))
        unfolded_text = tokenized_text.unfold(0, window_length, step_size)
        unfolded_mask = attention_mask.unfold(0, window_length, step_size)

        num_batches = math.ceil(len(unfolded_text)/batch_size)
        encoded_texts = []
        for i in range(num_batches):
            batch_text = unfolded_text[i*batch_size:(i+1)*batch_size]
            batch_mask = unfolded_mask[i*batch_size:(i+1)*batch_size]
            batch = {'input_ids': batch_text.to(device=device), 'attention_mask': batch_mask.to(device=device)}
            out_features = model.forward(batch) # Weird that the SentenceTransformer explicitly calls forward
            embeddings = out_features['sentence_embedding']
            encoded_text = embeddings.detach().cpu()
            encoded_texts.append(encoded_text)
        encoded_texts = torch.cat(encoded_texts, dim=0)
        summary_encoding = torch.sum(encoded_text, dim=0)
        return summary_encoding.detach().cpu().numpy()

def encode_packaged_patents(packaged, doc_start=None, doc_end=None, batch_size=16, window_length=512):
    with zipfile.ZipFile(packaged) as z:
        document_files = defaultdict(lambda: {'patent_info': None, 'images': []})
        n_infos = 0
        for info in z.infolist():
            n_infos += 1
            patent, filename = info.filename.split('/')
            base, ext = filename.split('.')
            if ext == 'json':
                document_files[patent]['patent_info'] = info
            elif ext == 'tif':
                document_files[patent]['images'].append(info)
        
        
        text_patents = []
        
        for patent, infos in tqdm(sorted(document_files.items())):
            with z.open(infos['patent_info']) as fp:
                patent_info = json.load(fp)
                

            abstract = patent_info['abstract']['en']
            description = patent_info['description']['en']
            claims = patent_info['claims']['en']
            applicants = patent_info['applicants']
            publication_date = patent_info['publication_date']
            ipc_classes = patent_info['ipc_classes']
            
            vectors = dict(abstract_vector=encode_text(abstract, model, batch_size=batch_size, window_length=window_length),
                        description_vector=encode_text(description, model, batch_size=batch_size, window_length=window_length),
                        claims_vector = encode_text(claims, model, batch_size=batch_size, window_length=window_length))
        
            patent_repr = dict(patent_number=patent,
            vectors=vectors,
                            applicants=','.join(applicants),
                            publication_date=publication_date, 
                            ipc_classes=ipc_classes)
                    
            
            text_patents.append(patent_repr)

            
    return text_patents

packaged = [Path('F:/datasets/PRV_KEMI_DATA/packaged_patents/english_netto_list.zip'),
            Path('F:/datasets/PRV_KEMI_DATA/packaged_patents/complement_english.zip'),
            Path('F:/datasets/PRV_KEMI_DATA/packaged_patents/english_random_sample.zip')]

output_dir = Path('F:/datasets/PRV_KEMI_DATA/patent_sbert_no_overlap/')
output_dir.mkdir(exist_ok=True)
for p in packaged:
    text_patents = encode_packaged_patents(p)
    basename = p.with_suffix('').name
    with open(output_dir / f'patent_sbert_no_images_{basename}.pkl', 'wb') as fp:
        pickle.dump(text_patents, fp)