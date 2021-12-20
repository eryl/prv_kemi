import argparse
from pathlib import Path
import json
import math
import re
import datetime
import random
from collections import Counter
import time

from requests.models import HTTPError

from tqdm import tqdm, trange
import epo_ops

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


def cleanup_class(class_str):
    return class_str.replace('/', '-')


def sample_random_patents(week, count, client):
    week_start, week_end = week
    
    patents = []
    begin_date_str = week_start.strftime('%Y%m%d')
    end_date_str = week_end.strftime('%Y%m%d')
    cql = f'pn=EP and pd="{begin_date_str} {end_date_str}"'
    req = client.published_data_search(cql, range_begin=1, range_end=2)  # We limit the range to limit how much date we request
    query_response = json.loads(req.content)
    total_count = int(query_response['ops:world-patent-data']['ops:biblio-search']['@total-result-count'])
    end_range = min(2000, total_count)

    search_result_numbers = sorted(random.sample(range(end_range), count))
    collected_ranges = []
    current_range_start = search_result_numbers[0]
    current_range = [current_range_start]
    for search_result_number in search_result_numbers[1:]:
        if search_result_number - current_range_start > 99:
            collected_ranges.append(current_range)
            current_range_start = search_result_number
            current_range = [current_range_start]
        else:
            current_range.append(search_result_number)
    collected_ranges.append(current_range)

    sampled_patents = []
    for search_range in tqdm(collected_ranges, desc="Retriving documents", leave=False):
        try:
            start_range = min(search_range)
            end_range = max(search_range)
            req = client.published_data_search(cql, range_begin=start_range, range_end=end_range)  # We limit the range to limit how much date we request
            # Since this is the tightest loop, let's ad ad-hoc throttling here
            # h = req.headers
            # throttling_control = h['x-throttling-control']
            # m = re.search(r'search=(\w+):(\d+)', throttling_control)
            # if m is not None:
            #     status, n_requests = m.groups()
            #     if status != 'green':
            #         print("Self-throttling")
            #         time.sleep(120)
            query_response = json.loads(req.content)
            patents = extract_patents(query_response)
            selected_patents = [patents[x - start_range] for x in search_range]
            sampled_patents.extend(selected_patents)
        except HTTPError as e:
            print(f'Error retrieving data for dates {start_range}-{end_range}, {e}')
            raise e
        
    return sampled_patents


def search_patents_in_classes(ipc_classes, client, output_dir: Path, overwrite=False, random_seed=None):
    for year, class_counts in tqdm(ipc_classes.items(), desc='Year'):
        year = int(year)
        if random_seed is not None:
            # We base the seed on the year, so that with a given 
            # seed and year the same documents will be sampled
            # This makes the sampling stable with regards to 
            # adding or removing years
            random.seed(year+random_seed)
        total_patents = sum(class_counts.values())
        start_date = datetime.datetime(year=year, month=1, day=1)
        end_date = datetime.datetime(year=year+1, month=1, day=1)
        
        weeks = []
        week_start = start_date
        week_dt = datetime.timedelta(days=7)
        while week_start < end_date:
            week_end = week_start + week_dt
            weeks.append((week_start, week_end))
            week_start = week_end

        patents_per_week = Counter(random.choices(weeks, k=total_patents))
        for week, count in tqdm(patents_per_week.items(), desc='Week'):
            week_start, week_end = week
            begin_date_str = week_start.strftime('%Y%m%d')
            end_date_str = week_end.strftime('%Y%m%d')
            output_path = output_dir / f'random_sample_{begin_date_str}_{end_date_str}.txt'
            if not output_path.exists() or overwrite:
                try:
                    sampled_patents = sample_random_patents(week, count, client)
                    with open(output_path, 'w') as fp:
                        fp.write('\n'.join(sampled_patents))
                except HTTPError as e:
                    print(f'Error retrieving data for dates {begin_date_str}-{end_date_str}, {e}')
                    h = e.response.headers
                    if 'x-rejection-reason' in h and h['x-rejection-reason'] == 'ThrottlingControlQuota':
                        wait_time = int(h['retry-after'])
                        raise e

                except IndexError as e:
                    print(f'Index error when retrieving data for dates {begin_date_str}-{end_date_str}, {e}')




def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading list of documents not constrained by classs, but by time")
    parser.add_argument('sample_file', help='Json file with desired number of patents per year', type=Path)
    parser.add_argument('--output-dir', help="Directory to ouput document files to", 
        type=Path, default=Path())
    parser.add_argument('--api-keys', help='JSON file with the API key',
                        type=Path, default=Path('../api_key.json'))
    parser.add_argument('--overwrite', help='If flag is set, overwrite data in output dir. '
                        'If not set, data which is already present will not be downloaded again', 
                        action='store_true')
    parser.add_argument('--random-seed', type=int, default=1729)
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
    
    with open(args.sample_file, 'r') as fp:
        yearly_classes = json.load(fp)
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    search_patents_in_classes(yearly_classes, client, args.output_dir, overwrite=args.overwrite, random_seed=args.random_seed)


if __name__ == '__main__':
    main()
