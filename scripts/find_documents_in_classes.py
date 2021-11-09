import argparse
from pathlib import Path
import json
import math
from requests.models import HTTPError

from tqdm import tqdm, trange
import epo_ops


def determine_yearly_range(client, cql, year_range):
    '''return a sequence of year ranges where each range will return less than 2000 patents'''
    begin_year, end_year = year_range
    year_instantiated_cql = cql.format(begin_year=begin_year, end_year=end_year)
    print(year_instantiated_cql)
    req = client.published_data_search(year_instantiated_cql, range_begin=1, range_end=2)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    if total_count < 2000:
        return (year_range,)
    else:
        year_range = int((end_year - begin_year)/2)
        first_range = (begin_year, begin_year+year_range)
        second_range = (begin_year+year_range + 1, end_year)   # +1 since the ranges are inclusive (I think?)
        return determine_yearly_range(client, cql, first_range) + determine_yearly_range(client, cql, second_range)


def extract_patents(query_response):
    docs = query_response['ops:world-patent-data']['ops:biblio-search']['ops:search-result']['ops:publication-reference']
    if not isinstance(docs, list):
        # In the rare case that we get a single result, it's not returned as a JSON array, but as a singleton object
        docs = [docs]
    document_ids = []
    for doc in docs:
        document_id = doc['document-id']
        country = document_id['country']['$']
        doc_number = document_id['doc-number']['$']
        kind_code = document_id['kind']['$']
        doc_str = f'{country}{doc_number}.{kind_code}'
        document_ids.append(doc_str)
    return document_ids


def get_class_patents(client, cql):
    patents = []
    req = client.published_data_search(cql, range_begin=1, range_end=100)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    patents.extend(extract_patents(query_response))

    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    n_requests = int(math.ceil(total_count / 100))
    for i in trange(1, n_requests, desc="Retriving documents", leave=False):
        start_range = i*100+1
        end_range = (i+1)*100
        req = client.published_data_search(cql, range_begin=start_range, range_end=end_range)  # We limit the range to limit how much date we request
        query_response = json.loads(req.content)
        patents.extend(extract_patents(query_response))
    return patents


def search_patents_in_classes(ipc_classes, client, output_dir: Path, year_range=(2000,2021), overwrite=False, multiple_years=False):
    '''Search for patents belonging to the given classes'''
    for ipc_class in ipc_classes:
        if multiple_years:
            output_path = output_dir / f'{ipc_class}_{year_range[0]}-{year_range[1]}.csv'
            if not output_path.exists() or overwrite:
                # We're going to do a gradual divide and conquer until the hit results are below 2000 since that is the maximum
                cql = f'ipc={ipc_class}' + ' and pn=EP and pd="{begin_year} {end_year}"'
                valid_year_ranges = determine_yearly_range(client, cql, year_range)
                documents = []
                for begin_year, end_year in valid_year_ranges:
                    year_instantiated_cql = cql.format(begin_year=begin_year, end_year=end_year)
                    documents.extend(get_class_patents(client, year_instantiated_cql))
                with open(output_path, 'w') as fp:
                    fp.write('\n'.join(documents))
        else:
            begin_year, end_year = year_range
            for year in trange(begin_year, end_year+1, desc='Year'):
                try:
                    output_path = output_dir / f'{ipc_class}_{year}.csv'
                    if not output_path.exists() or overwrite:
                        with open(output_path, 'w') as fp:
                            cql = f'ipc={ipc_class} and pn=EP and pd="{year}"'
                            documents = get_class_patents(client, cql)
                            fp.write('\n'.join(documents))
                except HTTPError as e:
                    print(f'Error retrieving data for year {year}')


def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading list of documents belonging to a certain class")
    parser.add_argument('classes_file', help='Text file with a list of all IPC classes to go through', type=Path)
    parser.add_argument('--output-dir', help="Directory to ouput document files to", 
        type=Path, default=Path())
    parser.add_argument('--api-keys', help='JSON file with the API key',
                        type=Path, default=Path('../api_key.json'))
    parser.add_argument('--overwrite', help='If flag is set, overwrite data in output dir. '
                        'If not set, data which is already present will not be downloaded again', 
                        action='store_true')
    parser.add_argument('--year-range', help="Range to limit search to.", type=int, nargs=2, default=(1970,2021))
    parser.add_argument('--multiple-years', help="If this flag is set, download data for multiple years. Otherwise take one year at a time", action='store_true')
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

    with open(args.classes_file, 'r') as fp:
        ipc_classes = [line.strip() for line in fp]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    search_patents_in_classes(ipc_classes, client, args.output_dir, year_range=args.year_range, overwrite=args.overwrite, multiple_years=args.multiple_years)


if __name__ == '__main__':
    main()
