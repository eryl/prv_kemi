# Patent project scripts

This repo holds scripts for the patent project

## Environment
Use anaconda to setup the environment

`conda env create -f environment.yml`

This creates a new environment called `epo-ops`. Activate it by running

`conda activate epo-ops`

Now you need to install the python client package. This notebook relies on a fork. Clone it to a suitable location:

`git clone git@github.com:eryl/python-epo-ops-client.git`

Now go to that location and install a development version using pip:

```
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
There are to scripts for downloading patents `.scripts/retrieve_documents_epo_eps.py` and `.scripts/retrieve_documents_epo_ops.py`, the former uses the _European Publication Server_ and the latter the _Open Patent Service_. EPS is generally recommended but is limited to a quota of 5GB per week. The documents from OPS do not include all figures in a document, only those listed under the "images" API endpoint (typically any figures at the end of the documents). OPS also has additional throttling quotas which makes downloads slower, and requires the API keys.

Both scripts expects as ana argument a path to a text file where each row is an EP patent number formattet like "EP0000022.A1". For example, to download all patents listed in the file `examples_and_data/netto_list.txt`, run the command:

```python
$ python scripts/retrieve_documents_epo_eps.py examples_and_data/netto_list.txt
```

