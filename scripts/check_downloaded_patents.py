import argparse
from pathlib import Path
import json
import datetime
import zipfile

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
from zipfile import ZipFile
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from tqdm import tqdm, trange
import datetime
import random
import json
import shutil


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

def load_images(patent_path):
    with ZipFile(patent_path) as patent_zip:
        images = []
        for fileinfo in patent_zip.infolist():
            *parents, filename = fileinfo.filename.split('/')
            *baseparts, ext = filename.split('.')
            if ext == 'tif':
                with patent_zip.open(fileinfo) as fp:
                    image = fp.read()
                    images.append((filename, image))
        return images


def numbered_text(paragraph):
    text = ''
    if 'num' in paragraph.attrib:
        num = paragraph.attrib['num']
        text = f'[{num}] '
    text += ''.join(paragraph.itertext())
    return text

def get_texts(elements):
    text_dict = {}
    
    for element in elements:
        lang = element.attrib['lang']
        texts = '\n'.join(numbered_text(c) for c in element)
        text_dict[lang] = texts
    return text_dict

def extract_patent_info(patent_path):
    patent_info = dict()
    root = load_patent_xml(patent_path)
    # The root element is the 'ep-patent-document', which has an attribute called date-publ, the publication date
    publication_date_str = root.attrib['date-publ']
    #publication_date = datetime.datetime.strptime(publication_date_str, '%Y%m%d')
    patent_info['publication_date'] = publication_date_str

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

    patent_info['abstract'] = get_texts(root.findall('abstract'))
    patent_info['claims'] = get_texts(root.findall('claims'))
    patent_info['description'] = get_texts(root.findall('description'))
    
    applicants = root.findall('.//SDOBI//B711/snm')
    text_applicants = [e.text for e in applicants]
    patent_info['applicants'] = text_applicants

    language, = root.findall('.//SDOBI/B200/B260')
    language_text = language.text
    patent_info['language'] = language_text


    return patent_info

def main():
    parser = argparse.ArgumentParser(
        description="Script for dowloading list of documents belonging to a certain class")
    parser.add_argument('patent_directory', help='Directory containing the patents to package', type=Path)
    args = parser.parse_args()

    patent_list = set(args.patent_directory.glob('EP*.zip'))
    
    broken_files = []

    
    for patent_file in tqdm(patent_list, desc='Patent files'):
        try:
            patent_info = extract_patent_info(patent_file)
        except zipfile.BadZipFile as e:
            broken_files.append(patent_file)

    broken_dir = args.patent_directory / 'broken_files'            
    broken_dir.mkdir(exist_ok=True)

    for broken_file in broken_files:
        shutil.move(broken_file, broken_dir)

if __name__ == '__main__':
    main()