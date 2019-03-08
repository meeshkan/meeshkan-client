# Using Meeshkan in developing Kaggle kernels

Example of using Meeshkan in a Kaggle kernel using the data from
[Petfinder.my adoption prediction competition](https://www.kaggle.com/c/petfinder-adoption-prediction).

## Setup

Install dependencies:
```bash
$ pip install -r requirements.txt
```

## Download data

#### Using Kaggle API

First check that your [Kaggle command-line-tool](https://github.com/Kaggle/kaggle-api) has been correctly setup,
i.e., that your `~/.kaggle/kaggle.json` exists and contains your API key.

Download competition data to `input/` with the following command:

```bash
$ kaggle competitions download -c petfinder-adoption-prediction -p input
```

This will take a few minutes. Once finished, unzip the input:

```bash
$ ./unzip_input.sh
```

#### Downloading manually

Download the data manually from [here](https://www.kaggle.com/c/petfinder-adoption-prediction/data) and unzip it in `input/`.

## Pushing a kernel to Kaggle

This assumes that you have `kaggle` command-line tool setup as explained [here](#using-kaggle-api). Before a kernel
in the folder `kernel/` can be pushed to Kaggle from command-line, it needs the metadata file `kernel-metadata.json` in the folder `kernel/`. You can create it either by running `kaggle kernels init -p kernel` to initialize the
file, or check [kernel-metadata-example.json](./kernel/kernel-metadata-example.json)
for reference and copy it to `kernel-metadata.json`.

Once you're happy with the kernel and metadata has been setup, push it to Kaggle for execution:
```bash
$ kaggle kernels push -p kernel
```

Note that all kernels are private by default.
