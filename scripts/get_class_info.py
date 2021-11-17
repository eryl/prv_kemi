import argparse
from pathlib import Path
import json
import datetime

from requests.models import HTTPError

from tqdm import tqdm, trange
from zipfile import ZipFile
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

import datetime
import random
import json
from pathlib import Path
import re
import json
from collections import defaultdict,  Counter
import datetime
import random
from zipfile import ZipFile
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter


def load_patent_xml(patent_path):
    with ZipFile(patent_path) as patent_zip:
        filenames = [zipinfo.filename for zipinfo in patent_zip.infolist()]
        # We're just assuming the only XML apart from TOC.xml is the one we're looking for
        # Since the name of this document is based on the application number, not the 
        # publication number, we have to scan for it manually
        doc_xml = None
        for filename in filenames:
            *base, ext = filename.split('.')
            if ext == 'xml' and filename.lower() != 'toc.xml':
                doc_xml = filename
        if doc_xml is None:
            raise ValueError(f"Unable to find document xml for zipfile {patent_path}")
        
        with patent_zip.open(doc_xml) as patent_xml_fp:
            xml_str = str(patent_xml_fp.read(), encoding='utf8')
            root = ET.fromstring(xml_str)
            return root


def extract_patent_info(patent_path):
    patent_info = dict()
    root = load_patent_xml(patent_path)
    # The root element is the 'ep-patent-document', which has an attribute called date-publ, the publication date
    publication_date_str = root.attrib['date-publ']
    publication_date = datetime.datetime.strptime(publication_date_str, '%Y%m%d')
    patent_info['publication_date'] = publication_date

    doc_country = root.attrib['country']
    doc_number = root.attrib['doc-number']
    doc_kind = root.attrib['kind']
    patent_info['document_number'] = f'{doc_country}{doc_number}.{doc_kind}'

    ipcr_classes = root.findall('.//SDOBI//classification-ipcr/text')
    text_classes = [e.text for e in ipcr_classes]
    # The class string has the form 'A61K  38/44        20060101AFI20130522BHEP        '
    # We first split by white space and only select the first two parts
    split_classes = [text.split() for text in text_classes]
    selected_parts = [(main_class, sub_class) for main_class, sub_class, *_ in split_classes]
    patent_info['ipc_classes'] = selected_parts

    return patent_info



def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading list of documents belonging to a certain class")
    parser.add_argument('netto_list_patents', help='Directory containing the patents in the netto list', type=Path)
    parser.add_argument('--output-directory', help="Directory to output files to", type=Path, default=Path())
    parser.add_argument('--sample-ratio', help="How many complement patents to sample relative to the netto list", type=float, default=1)
    parser.add_argument('--random-seed', help="Constant to seed the random number generator with for repreducability", type=int, default=None)
    parser.add_argument('--most-common-k', type=int, default=20)
    args = parser.parse_args()

    random.seed(args.random_seed)
    netto_list_patents = set(args.netto_list_patents.glob('EP*.zip'))

    downloaded_patents = set()
    yearly_patents = defaultdict(set)
    yearly_patent_classes = defaultdict(Counter)
    yearly_patents_to_classes = defaultdict(dict)
    error_patents = []
    for patent_path in tqdm(netto_list_patents, desc='Processing patent files', leave=False):
        try:
            patent_info = extract_patent_info(patent_path)
            patent_number = patent_info['document_number']
            downloaded_patents.add(patent_number)
            year = patent_info['publication_date'].year
            patent_classes = patent_info['ipc_classes']
            yearly_patents[year].add(patent_number)
            yearly_patent_classes[year].update(patent_classes)
            yearly_patents_to_classes[year][patent_number] = patent_classes
        except BaseException as e:
            #print(f"Error with patent {patent_path}, {e}")
            error_patents.append(patent_path)
    
    output_dir = args.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'error_loading_patents.txt', 'w') as fp:
        fp.write('\n'.join(error_patents))
    
    with open(output_dir / 'downloaded_netto_patents.txt', 'w') as fp:
        fp.write('\n'.join(sorted(downloaded_patents)))
    
    with open(output_dir / 'yearly_patents.json', 'w') as fp:
        json_prepped_yearly_patents = {year: sorted(patents) for year, patents in yearly_patents.items()}
        json.dump(json_prepped_yearly_patents, fp, indent=2, sort_keys=True)

    with open(output_dir / 'yearly_patent_classes.json', 'w') as fp:
        json_prepped_yearly_patent_classes = {year: {f'{main_class} {sub_class}': count for (main_class, sub_class), count in class_counts.items()} for year, class_counts in yearly_patent_classes.items()}
        json.dump(json_prepped_yearly_patent_classes, fp, indent=2, sort_keys=True)

    # We first filter the clases based on the main class
    yearly_patent_classes_coarse = defaultdict(Counter)
    for year, class_counts in yearly_patent_classes.items():
        for (main_class, sub_class), count in class_counts.items():
            yearly_patent_classes_coarse[year][main_class] += count
    
    with open(output_dir /'yearly_coarse_patent_classes.json', 'w') as fp:
        json.dump(yearly_patent_classes_coarse, fp, sort_keys=True, indent=2)

    patent_classes = Counter()
    for year, class_counts in yearly_patent_classes.items():
        for ipc_class, count in class_counts.items():
            patent_classes[ipc_class] += count
    
    with open(output_dir/'fine_grained_by_rank.csv', 'w') as fp:
        row_format = '{main_class},{sub_class},{count}\n'
        fp.write(row_format.format(main_class='main_class', sub_class='sub_class', count='count'))
        for (main_class, sub_class), count in patent_classes.most_common():
            fp.write(row_format.format(main_class=main_class, sub_class=sub_class, count=count))
    
    main_classes = Counter()
    for year, class_counts in yearly_patent_classes_coarse.items():
        for main_class, count in class_counts.items():
            main_classes[main_class] += count

    most_common_coarse_20_set = set(main_class for main_class, count in main_classes.most_common(20))
    with open(output_dir / 'most_common_20_main_classes.txt', 'w') as fp:
        fp.write('\n'.join(most_common_coarse_20_set))


    most_common_by_year = {year: dict(class_counts.most_common(args.most_common_k)) for year, class_counts in yearly_patent_classes_coarse.items()}
    with open(output_dir / 'most_common_by_year.json', 'w') as fp:
        json.dump(most_common_by_year, fp, sort_keys=True, indent=2)

    samples_per_year = {year: int(len(patents)*args.sample_ratio) for year, patents in yearly_patents.items()}
    filtered_documents = defaultdict(dict)

    for year, patents_to_classes in yearly_patents_to_classes.items():
        for patent_number, classes in patents_to_classes.items():
            most_common_classes = most_common_by_year[year]
            common_class_occurance = [(main_class, most_common_classes[main_class]) for main_class, sub_class in classes if main_class in most_common_classes]
            if len(common_class_occurance) > 0:
                occured_classes, counts = zip(*common_class_occurance)
                total_count = sum(counts)
                class_probabilities = [count/total_count for count in counts]
                filtered_documents[year][patent_number] = (occured_classes, class_probabilities)

    desired_sample_size_max_k = defaultdict(Counter)
    for year, samples in samples_per_year.items():
        yearly_patent_classes = list(filtered_documents[year].values())
        for i in range(samples):
            (occured_classes, class_probabilities) = random.choice(yearly_patent_classes)
            [sampled_class,] = random.choices(occured_classes, weights=class_probabilities)
            desired_sample_size_max_k[year][sampled_class] += 1

    with open(output_dir / f'desired__max_k_sample_ratio{args.sample_ratio}.json', 'w') as fp:
        json.dump(desired_sample_size_max_k, fp, sort_keys=True, indent=2)





if __name__ == '__main__':
    main()