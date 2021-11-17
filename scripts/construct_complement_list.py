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

def load_search_results(search_result_path):
    m = re.match(r'([\w\d]+)_(\d+)-(\d+)\.txt', search_result_path.name)
    if m is not None:
        ipc_class, begin_date_str, end_date = m.groups()
        begin_date = datetime.datetime.strptime(begin_date_str, '%Y%m%d')
        with open(search_result_path) as fp:
            patent_numbers = [line.strip() for line in fp]
        return {ipc_class: {begin_date.year: patent_numbers}}
    else:
        print("not a match")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading list of documents belonging to a certain class")
    parser.add_argument('sample_list', help='JSON file detailing what classes to sample per year', type=Path)
    parser.add_argument('netto_list', help='Text file with the netto list to find complement for', type=Path)
    parser.add_argument('class_patents', help='Directory containing the class patents information', type=Path)
    parser.add_argument('--output-directory', help="Directory to output files to", type=Path, default=Path())
    parser.add_argument('--sample-ratio', help="How many complement patents to sample relative to the netto list", type=float, default=1)
    parser.add_argument('--random-seed', help="Constant to seed the random number generator with for repreducability", type=int, default=None)
    args = parser.parse_args()

    output_dir = args.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    random.seed(args.random_seed)
    with open(args.sample_list) as fp:
        desired_samples = json.load(fp)
    with open(args.netto_list) as fp:
        netto_list_patents = set(line.strip() for line in fp)
    search_results_files = list(args.class_patents.glob('*.txt'))

    # downloaded_patents = set()
    # yearly_patents = defaultdict(set)
    # yearly_patent_classes = defaultdict(Counter)
    # yearly_patents_to_classes = defaultdict(dict)
    # error_patents = []
    # for patent_path in tqdm(netto_list_patents, desc='Processing patent files', leave=False):
    #     try:
    #         patent_info = extract_patent_info(patent_path)
    #         patent_number = patent_info['document_number']
    #         downloaded_patents.add(patent_number)
    #         year = patent_info['publication_date'].year
    #         patent_classes = patent_info['ipc_classes']
    #         yearly_patents[year].add(patent_number)
    #         yearly_patent_classes[year].update(patent_classes)
    #         yearly_patents_to_classes[year][patent_number] = patent_classes
    #     except BaseException as e:
    #         #print(f"Error with patent {patent_path}, {e}")
    #         error_patents.append(patent_path)
    
    
    # with open(output_dir / 'error_loading_patents.txt', 'w') as fp:
    #     fp.write('\n'.join(error_patents))
    
    # with open(output_dir / 'downloaded_netto_patents.txt', 'w') as fp:
    #     fp.write('\n'.join(sorted(downloaded_patents)))
    

    # # We first filter the clases based on the main class
    # yearly_patent_classes_coarse = defaultdict(Counter)
    # for year, class_counts in yearly_patent_classes.items():
    #     for (main_class, sub_class), count in class_counts.items():
    #         yearly_patent_classes_coarse[year][main_class] += count
    
    # patent_classes = Counter()
    # for year, class_counts in yearly_patent_classes.items():
    #     for ipc_class, count in class_counts.items():
    #         patent_classes[ipc_class] += count
    
    # with open(output_dir/'fine_grained_by_rank.csv', 'w') as fp:
    #     row_format = '{main_class},{sub_class},{count}\n'
    #     fp.write(row_format.format(main_class='main_class', sub_class='sub_class', count='count'))
    #     for (main_class, sub_class), count in patent_classes.most_common():
    #         fp.write(row_format.format(main_class=main_class, sub_class=sub_class, count=count))
    

    # main_classes = Counter()
    # for year, class_counts in yearly_patent_classes_coarse.items():
    #     for main_class, count in class_counts.items():
    #         main_classes[main_class] += count

    # most_common_coarse_20 = main_classes.most_common(20)
    # most_common_coarse_20_set = set(main_class for main_class, count in main_classes.most_common(20))
    
            
    # with open(output_dir / 'most_common_20_main_classes.txt', 'w') as fp:
    #     fp.write('\n'.join(most_common_coarse_20_set))

    # most_common_coarse_20_map = dict(most_common_coarse_20)

    # samples_per_year = {year: int(len(patents)*args.sample_ratio) for year, patents in yearly_patents.items()}
    # filtered_documents = defaultdict(dict)

    # for year, patents_to_classes in yearly_patents_to_classes.items():
    #     for patent_number, classes in patents_to_classes.items():
    #         common_class_occurance = [(main_class, most_common_coarse_20_map[main_class]) for main_class, sub_class in classes if main_class in most_common_coarse_20_map]
    #         if len(common_class_occurance) > 0:
    #             occured_classes, counts = zip(*common_class_occurance)
    #             total_count = sum(counts)
    #             class_probabilities = [count/total_count for count in counts]
    #             filtered_documents[year][patent_number] = (occured_classes, class_probabilities)
                

    # desired_sample_size = defaultdict(Counter)
    # for year, samples in samples_per_year.items():
    #     yearly_patent_classes = list(filtered_documents[year].values())
    #     for i in range(samples):
    #         (occured_classes, class_probabilities) = random.choice(yearly_patent_classes)
    #         [sampled_class,] = random.choices(occured_classes, weights=class_probabilities)
    #         desired_sample_size[year][sampled_class] += 1

    # with open(output_dir / f'desired_sample_size_with_sample_ratio_{args.sample_ratio}.json', 'w') as fp:
    #     json.dump(desired_sample_size, fp, sort_keys=True, indent=2)

    # # collated_search_results = defaultdict(lambda: defaultdict(set))
    # # for results_path in search_results_files:
    # #     class_docs = load_search_results(results_path)
    # #     if class_docs is not None:
    # #         for ipc_class, yearly_docs in class_docs.items():
    # #             for year, docs in yearly_docs.items():
    # #                 collated_search_results[year][ipc_class].update(docs)

    collated_complement_search_results = defaultdict(lambda: defaultdict(set))
    for results_path in search_results_files:
        class_docs = load_search_results(results_path)
        if class_docs is not None:
            for ipc_class, yearly_docs in class_docs.items():
                for year, docs in yearly_docs.items():
                    filtered_docs = [doc for doc in docs if doc not in netto_list_patents]
                    collated_complement_search_results[year][ipc_class].update(filtered_docs)
    
    collected_sampled_complement_docs = set()
    sampled_complement_docs = defaultdict(lambda: defaultdict(set))
    error_on_small_sample_size = False

    for year, class_sample_sizes in desired_samples.items():
        for ipc_class, class_sample_size in class_sample_sizes.items():
            # Remove any documents which we have sampled for other classes
            docs = collated_complement_search_results[int(year)][ipc_class] - collected_sampled_complement_docs
            if len(docs) < class_sample_size:
                error_str = f"The number of documents ({len(docs)}) for class {ipc_class} is less than the desired sample size {class_sample_size} for year {year}"
                
                if error_on_small_sample_size:
                    raise ValueError(error_str)
                else:
                    print(error_str)
                    sampled_docs = list(docs)
            else:
                sampled_docs = random.sample(list(docs), class_sample_size)

            sampled_complement_docs[year][ipc_class] = sampled_docs
            collected_sampled_complement_docs.update(sampled_docs)

    print(f"Number of sampled complement docs: {len(collected_sampled_complement_docs)}")

    with open(output_dir / 'sampled_complement_patents_by_year.json', 'w') as fp:
        json.dump(sampled_complement_docs, fp, indent=2, sort_keys=True)

    with open(output_dir / 'sampled_complement_patents.txt', 'w') as fp:
        fp.write('\n'.join(sorted(collected_sampled_complement_docs)))

    for year, ipc_classes_patents in sampled_complement_docs.items():
        with open(output_dir / f'sampled_complement_year_{year}.txt', 'w') as fp:
            for ipc_class, patents in ipc_classes_patents.items():
                fp.writelines(f'{patent_number}\n' for patent_number in patents)

    print("The intersection of the netto list and the complement is ", netto_list_patents.intersection(collected_sampled_complement_docs))
            


if __name__ == '__main__':
    main()