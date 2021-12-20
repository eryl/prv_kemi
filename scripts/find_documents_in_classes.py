import argparse
from pathlib import Path
import json
import math
import re
import datetime

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
        year_range = ((end_year - begin_year)/2)
        first_range = (begin_year, begin_year+year_range)
        second_range = (begin_year+year_range + 1, end_year)   # +1 since the ranges are inclusive (I think?)
        return determine_yearly_range(client, cql, first_range) + determine_yearly_range(client, cql, second_range)


def determine_date_ranges(client, ipc_class, date_range):
    '''return a sequence of date ranges where each range will return less than 2000 patents'''
    begin_date, end_date = date_range
    begin_date_str = begin_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')
    year_instantiated_cql = f'ipc={ipc_class} and pn=EP and pd="{begin_date_str} {end_date_str}"'
    #print(year_instantiated_cql)
    req = client.published_data_search(year_instantiated_cql, range_begin=1, range_end=2)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    if total_count < 2000:
        return (date_range,)
    else:
        timedelta = end_date-begin_date
        first_range = (begin_date, begin_date+timedelta/2)
        second_range = (begin_date+timedelta/2, end_date)   # +1 since the ranges are inclusive (I think?)
        return determine_date_ranges(client, ipc_class, first_range) + determine_date_ranges(client, ipc_class, second_range)
    

def prepare_date_ranges(client, ipc_class, year):
    cql = f'ipc={ipc_class}' + ' and pn=EP and pd={year}'
    req = client.published_data_search(cql, range_begin=1, range_end=2)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    if total_count < 2000:
        return (year_range,)
    else:
        date_ranges = determine_date_ranges(client, ipc_class, year)
        return date_ranges

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


def get_class_patents(client, ipc_class, date_range):
    patents = []
    begin_date, end_date = date_range
    begin_date_str = begin_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')
    cql = f'ipc={ipc_class} and pn=EP and pd="{begin_date_str} {end_date_str}"'
    req = client.published_data_search(cql, range_begin=1, range_end=100)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    patents.extend(extract_patents(query_response))

    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    if not total_count < 2000:
        raise ValueError(f"Total count is too much for class {ipc_class} and date range {date_range}")
    n_requests = int(math.ceil(total_count / 100))
    for i in trange(1, n_requests, desc="Retriving documents", leave=False):
        start_range = i*100+1
        end_range = (i+1)*100
        req = client.published_data_search(cql, range_begin=start_range, range_end=end_range)  # We limit the range to limit how much date we request
        query_response = json.loads(req.content)
        patents.extend(extract_patents(query_response))
    return patents

def cleanup_class(class_str):
    return class_str.replace('/', '-')

def get_missing_date_ranges(directory, ipc_class, date_range):
    year_class_files = list(directory.glob(f'{ipc_class}_*.txt'))
    query_start, query_end = date_range 
     # The algorithm below looks for gaps between tuples of start_date, end_date. 
     # By adding two dummy dates (query_start, query_start) and 
     # (query_end, query_end) these will show up in the missing date ranges
    existing_date_ranges = [(query_start, query_start), (query_end, query_end)]  
    for f in year_class_files:
        m = re.match(r'([\w\d]+)_(\d+)-(\d+)\.txt', f.name)
        if m is not None:
            ipc_class_, begin_date_str, end_date_str = m.groups()
            begin_date = datetime.datetime.strptime(begin_date_str, '%Y%m%d')
            end_date = datetime.datetime.strptime(end_date_str, '%Y%m%d')
            # We only add those files which have dates overlapping the query range
            if begin_date < query_end and end_date > query_start:
                existing_date_ranges.append((begin_date, end_date))
    existing_date_ranges.sort()
    merged_existing_date_ranges = []
    missing_date_ranges = []
    if existing_date_ranges:
        current_date_range = existing_date_ranges[0]
        for next_date_range in existing_date_ranges[1:]:
            current_start, current_end = current_date_range
            next_start, next_end = next_date_range
            if current_end < next_start:
                merged_existing_date_ranges.append(current_date_range)
                missing_date_range = (current_end, next_start)
                missing_date_ranges.append(missing_date_range)
                current_date_range = next_date_range
            else:
                current_date_range = (current_start, next_end)
        merged_existing_date_ranges.append(current_date_range)
    return missing_date_ranges, merged_existing_date_ranges

def search_patents_in_classes(ipc_classes, client, output_dir: Path, overwrite=False):
    for year, class_counts in ipc_classes.items():
        year = int(year)
        start_date = datetime.datetime(year=year, month=1, day=1)
        end_date = datetime.datetime(year=year+1, month=1, day=1)

        for ipc_class in tqdm(class_counts.keys(), desc='Processing classes', leave=False):
            # Just make a quick check for the  whole date range. If there's a file we skip it
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            cleaned_class = cleanup_class(ipc_class)

            query_date_ranges = []

            if not overwrite:
                # Determine whether there is something to do by looking at the existing date files
                missing_date_ranges, merged_existing_date_ranges = get_missing_date_ranges(output_dir, cleaned_class, (start_date, end_date))
                for missing_date_range in missing_date_ranges:
                    divided_date_ranges = determine_date_ranges(client, ipc_class, missing_date_range)
                    query_date_ranges.extend(divided_date_ranges)
            else:
                divided_date_ranges = determine_date_ranges(client, ipc_class, (start_date, end_date))
                query_date_ranges.extend(divided_date_ranges)

            for query_date_range in tqdm(query_date_ranges, desc='Query date range', leave=False):
                start_date, end_date = query_date_range
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                output_path = output_dir / f'{cleaned_class}_{start_date_str}-{end_date_str}.txt'
                if not output_path.exists() or overwrite:
                    try:
                        documents = get_class_patents(client, ipc_class, query_date_range)
                        with open(output_path, 'w') as fp:
                            fp.write('\n'.join(documents))
                    except HTTPError as e:
                        print(f'Error retrieving data for dates {start_date_str}-{end_date_str}, {e}')



def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading lists of documents belonging to a certain class")
    parser.add_argument('classes_file', help='Json file with map from years to IPC classes to go through', type=Path)
    parser.add_argument('--output-dir', help="Directory to ouput document files to", 
        type=Path, default=Path())
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
    
    # date_ranges = []
    # first_year, last_year = args.year_range
    # for year in range(first_year, last_year+1):
    #     begin_year = datetime.datetime(year=year, month=1, day=1)
    #     end_year = datetime.datetime(year=year+1, month=1, day=1)
    #     date_ranges.append((begin_year, end_year))
    
    with open(args.classes_file, 'r') as fp:
        yearly_classes = json.load(fp)
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    search_patents_in_classes(yearly_classes, client, args.output_dir, overwrite=args.overwrite)


if __name__ == '__main__':
    main()
