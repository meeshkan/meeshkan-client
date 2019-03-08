#!/usr/bin/env bash

cd input

for file in *.zip; do
    filename_without_extension=${file%.*}
    mkdir -p filename_without_extension
    unzip $file -d ${filename_without_extension}
done
