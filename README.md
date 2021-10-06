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
The Open Patent Service requires API keys. These should not be uploaded to this repo, instead create a `api_keys.json` file in the root of this repo with contents like:

```
{
	"key": "YOUR_API_KEY",
	"secret": "YOUR_API_SECRET"
}
```

The notebook script will load these attributes when it creates the client.