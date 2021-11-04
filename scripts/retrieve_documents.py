import argparse
from pathlib import Path
import json

from tqdm import tqdm
import epo_ops
from epo_ops.models import Epodoc
import requests

def fetch_data(client: epo_ops.Client, doc_id: str, output_dir: Path, overwrite=False):
    
    doc = Epodoc(doc_id)
    output_dir = output_dir / f'{doc.as_api_input()}'
    output_dir.mkdir(exist_ok=True, parents=True)

    status_file_path = output_dir / 'status.txt'
    if status_file_path.exists():
        with open(status_file_path, 'r') as fp:
            status = fp.read()
            if status == 'Missing EPO document':
                return
            elif  status == 'Done processing' and not overwrite:
                return

    for endpoint in ["fulltext", "biblio", "description", "claims", "images"]:
        #print("Get", endpoint)
        output_path = output_dir / f'{endpoint}.json'
        if overwrite or not output_path.exists():
            try:
                req = client.published_data('publication', doc, endpoint=endpoint)
                with open(output_path, 'wb') as fp:
                    fp.write(req.content)
            except requests.HTTPError as e:
                print(f"Received HTTP error {e} for document {doc_id} endpoint {endpoint}")
                with open(status_file_path, 'w') as fp:
                    fp.write('Missing EPO document')
                return
            
    with open(output_dir / 'images.json', 'r') as fp:
        image_query_json = json.load(fp)
    
    image_inquery_result = image_query_json['ops:world-patent-data']['ops:document-inquiry']['ops:inquiry-result']['ops:document-instance']
    if isinstance(image_inquery_result, dict):
        image_inquery_result = [image_inquery_result]
    
    for res in image_inquery_result:
        if res.get('@desc', None) == 'Drawing':
            n_pages = int(res['@number-of-pages'])
            request_url = res['@link']
            for i in range(1, n_pages+1):
                name = f'{i:02}'
                image_output_dir = output_dir / 'Drawing'
                image_output_dir.mkdir(exist_ok=True)
                output_path = image_output_dir / f'{name}.tiff'
                if overwrite or not output_path.exists():
                    req = client.image(request_url, range=i,
                                    document_format='application/tiff')
                    with open(output_path, 'wb') as fp:
                        fp.write(req.content)

    with open(status_file_path, 'w') as fp:
        fp.write('Done processing')

    # # Fetch images
    # endpoint = "images"
    # tree = ET.parse(f'../{doc.as_api_input()}/{endpoint}.xml')
    # # Extract image paths
    # paths = [e.attrib['link'] for e in tree.getroot().iter() if 'link' in e.attrib]
    # # Get and write to disk
    # for p in paths:
    #     print("Get", p)
    #     req = client.image(p, range=1)
    #     name = p.split('/')[-1]
    #     with open(f'../{doc.as_api_input()}/{name}.tiff', 'wb') as fp:
    #         fp.write(req.content)


def main():
    parser = argparse.ArgumentParser(
        description="Script for downloading documents from the EPO OPS")
    parser.add_argument(
        'document_numbers', help='JSON file with a list of all documents to fetch', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path())
    parser.add_argument('--api-keys', help='JSON file with the API key',
                        type=Path, default=Path('../api_key.json'))
    parser.add_argument('--overwrite', help='If flag is set, overwrite data in output dir. '
                        'If not set, data which is already present will not be downloaded again', 
                        action='store_true')
    args = parser.parse_args()

    middlewares = [
        # epo_ops.middlewares.Dogpile(), #No dogpile support on windows
        epo_ops.middlewares.Throttler(),
    ]

    with open(args.api_keys, 'r') as fp:
        api_keys = json.load(fp)

    client = epo_ops.Client(
        key=api_keys['key'],
        secret=api_keys['secret'],
        middlewares=middlewares,
        accept_type='json'
    )

    with open(args.document_numbers, 'r') as fp:
        documents = [line.strip() for line in fp]

    for doc_id in tqdm(documents, desc="Fetching documents"):
        fetch_data(client, doc_id, args.output_dir)


if __name__ == '__main__':
    main()
