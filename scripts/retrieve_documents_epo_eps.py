import argparse
from pathlib import Path
import json

from tqdm import tqdm
import requests

EPS_URL = 'https://data.epo.org/publication-server/rest/v1.2/patents/{}/document.zip'

def fetch_data(doc_id: str, output_dir: Path, overwrite=False):
    doc_id = 'NW'.join(doc_id.split('.'))
    output_path = output_dir / f'{doc_id}.zip'
    if overwrite or not output_path.exists():
        doc_url = EPS_URL.format(doc_id)
        req = requests.get(doc_url)
        req.raise_for_status()
        with open(output_path, 'wb') as fp:
            fp.write(req.content)

def main():
    parser = argparse.ArgumentParser(description="Script for downloading documents from the EPO Publication Server")
    parser.add_argument('document_numbers', nargs='*', 
                        help='JSON file with a list of all documents to fetch6', 
                        type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path())
    parser.add_argument('--overwrite', 
                        help='If flag is set, overwrite data in output dir. '
                        'If not set, data which is already present will not be downloaded again', 
                        action='store_true')
    args = parser.parse_args()
    documents = []

    for docnumber_file in args.document_numbers:
        with open(docnumber_file, 'r') as fp:
            
            documents.extend(line.strip() for line in fp)

    
    args.output_dir.mkdir(exist_ok=True, parents=True)
    for doc_id in tqdm(documents, desc="Fetching documents"):
        fetch_data(doc_id, args.output_dir)


if __name__ == '__main__':
    main()
