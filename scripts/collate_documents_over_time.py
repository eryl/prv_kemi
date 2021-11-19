import argparse
from pathlib import Path
import re
import datetime
import json

from collections import defaultdict
from tqdm import tqdm


def main():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('doc_dir', help="Directory containing the documents to collate", type=Path)
    parser.add_argument('--output-dir', help="Where to write the collated files to", type=Path, default=Path())
    args = parser.parse_args()

    doc_files = sorted(args.doc_dir.glob('*.txt'))

    yearly_docs = defaultdict(set)
    
    for doc_file in tqdm(doc_files, desc="Document files"):
        m = re.match(r'[\w_]+_(\d+)_(\d+).txt', doc_file.name)
        if m is not None:
            begin_date_str, end_date_str = m.groups()
            begin_date = datetime.datetime.strptime(begin_date_str, '%Y%m%d')
            end_date = datetime.datetime.strptime(end_date_str, '%Y%m%d')
            year = begin_date.year
            with open(doc_file) as fp:
                docs = set(line.strip() for line in fp)
                yearly_docs[year].update(docs)
    
    args.output_dir.mkdir(exist_ok=True, parents=True)
    with open(args.output_dir / 'yearly_docs.json', 'w') as fp:
        json.dump({year: sorted(docs) for year, docs in yearly_docs.items()}, fp, sort_keys=True, indent=2)
    
    for year, docs in yearly_docs.items():
        with open(args.output_dir / f'collated_docs_{year}.txt', 'w') as fp:
            fp.write('\n'.join(sorted(docs)))


if __name__ == '__main__':
    main()