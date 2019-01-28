# Using Meeshkan in developing Kaggle kernels

## Instructions

Install dependencies:
```bash
$ pip install -r requirements.txt
```

Check that your [Kaggle command-line-tool](https://github.com/Kaggle/kaggle-api) has been correctly setup,
i.e., that your `~/.kaggle/kaggle.json` exists and contains the correct API key.

Download competition data to `input`:

```bash
$ kaggle competitions download -c petfinder-adoption-prediction -p input
```

This will take a few minutes. Once finished, unzip the input:

```bash
$ ./unzip_input.sh
```

Next step is to create the metadata file `kernel-metadata.json` for the kernel
in `kernel/`. You can either run `kaggle kernels init -p kernel` to initialize the
file or check [kernel-metadata-example.json](./kernel/kernel-metadata-example.json)
for reference.

Once you're happy with the kernel, push it to Kaggle for execution:
```bash
$ kaggle kernels push -p kernel
```
