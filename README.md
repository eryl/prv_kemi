# EPO document retrieval and analysis

This repo holds scripts for downloading EPO patent data, as well as sampling documents according to some criteria. Parts of the scripts rely on the EPO OPS API, and you need to register a user to use the service at https://www.epo.org/searching-for-patents/data/web-services/ops.html.

## Environment
Use anaconda to setup the environment

`conda env create -f environment.yml`

This creates a new environment called `epo-data`. Activate it by running

`conda activate epo-data`

Now you need to install the python client package. This notebook relies on a fork. Clone it to a suitable location:

`git clone git@github.com:eryl/python-epo-ops-client.git`

Now go to that location and install a development version using pip:

``` bash
cd python-epo-ops-client
git checkout fixes  # This branch contains some small changes of the client
pip install -e .  # Install a "development" version of the package
```

## API Keys
The Open Patent Service requires API keys. Register a user at https://www.epo.org/searching-for-patents/data/web-services/ops.html to be able to generate API key and secret. Create a `api_keys.json` file in the root of this repo with contents like:

```
{
	"key": "YOUR_API_KEY",
	"secret": "YOUR_API_SECRET"
}
```

The notebooks and scripts will load these attributes when it creates the client. 

## Notebooks and scripts

Notebooks for various kinds of analysis and experimentation can be found in `./notebooks/`. These are generally not for the automated parts of the repository, that can instead be found in `./scripts/`.

### Scripts for retrieving patents
There are two scripts for downloading patents `.scripts/retrieve_documents_epo_eps.py` and `.scripts/retrieve_documents_epo_ops.py`, the former uses the _European Publication Server_ and the latter the _Open Patent Service_. EPS is generally recommended but is limited to a quota of 5GB per week. The documents from OPS do not include all figures in a document, only those listed under the "images" API endpoint (typically any figures at the end of the documents). OPS also has additional throttling quotas which makes downloads slower, and requires the API keys.

Both scripts expects as an argument a path to a text file where each row is an EP patent number formattet like "EP0000022.A1". For example, to download all patents listed in the file `examples_and_data/netto_list.txt` and save them to the directory `netto_patents/`, run the command:

```bash
$ python scripts/retrieve_documents_epo_eps.py examples_and_data/netto_list.txt --output-dir netto_patents
```

*Note:* If no output directory is given, the files are saved to the current working directory.

### Scripts for sampling negative patents
In this project, we needed to summarize information about the patents in the _positive_ class (the netto list) to be able to construct negative samples. The script `scripts/get_class_info.py` goes through patents in a directory and summarizes their IPC class composition. It also produces a file of suggested classes to sample from to get a negative sample with a similar class composition as the positive class.

To use this script run:

```bash
$ python scripts/get_class_info.py netto_patents --output-dir netto_class_statistics
```

This will produce a number of files for IPC-class statistics for the downloaded patents. The file `desired_max_k_sample_ratio_1.0.json` contains the suggested classes from which to produce a negative sample.


### Searching for patents
Two different methods for searching for negative patents is implemented, "complement" and "random" search. Complement search tries to find negative documents in the same IPC classes as the positive documents, while the random search is only constrained to follow the same year distribution as the positives. Examples of outputs can be found in `examples_and_data/search_results`. Due to how unstable the search API can be (with harsh throttling), the search is done piecemeal and saved in multiple files. The search uses a constant random seed, so rerunning the samme commands will give the same output and any results not saved to file will be retrieved again.

#### Sample in the same classes as the positive class

To sample files, we first collect lists of potential documents to sample from. This uses the OPS API to search for documents belonging to a certain class. To download lists of patents generated from the `class_info.py` script, run

```bash
$ python scripts/find_documents_in_classes.py netto_class_statistics/desired_max_k_sample_ratio_1.json --output-dir complement_document_lists
```
To  summarize the search results, use the script `scripts/construct_complement_list.py`. This will collect the sample to a number of file collated by year which can be used as inputs to `scripts/retrieve_docuiments_epo_eps.py` as above to retrieve the documents.

#### Sample randomly in the same date range as the positive class
The previous method samples in roughly the same class statistics as the positive class. We can instead sample from all published patents for the same date ranges as the positive class by using:

```bash
$ python scripts/find_documents_over_time.py netto_class_statistics/desired_max_k_sample_ratio_1.json --output-dir random_document_lists
```

To summarize the random search results, use the script `scripts/collate_documents_over_time.py`. It will summarize the whole list into a list of patent ids in one file per year. This list can then be used with `scripts/retrieve_docuiments_epo_eps.py` as above to retrieve the documents.

## Packaging downloaded patents
The downloaded patents are all in zip-files. Most contain a `.pdf` version of the patent as well which makes the total size about twice as large as we need. To exctract only the parts of the patents actually used in the analysis, a script is provided called `scripts/extract_and_package_patents.py`. Given a directory as argument, it finds all the downloaded patent documents in the directory and extracts the information used in this project and packages it all into one large zip archive.


