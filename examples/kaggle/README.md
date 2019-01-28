# Using Meeshkan in developing Kaggle kernels

## Instructions

Install dependencies:
```bash
$ pip install -r requirements.txt
```

Check that your [Kaggle command-line-tool](https://github.com/Kaggle/kaggle-api) has been properly setup,
i.e., that your `~/.kaggle/kaggle.json` exists and contains the correct API key.

Download competition data to `input`:

```bash
$ kaggle competitions download -c petfinder-adoption-prediction -p input
```

This will take a few minutes. Once finished, unzip the input:

```bash
$ ./unzip_input.sh
```
