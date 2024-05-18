#!/bin/bash

while IFS= read -r pattern; do
    echo "Removing files and directories matching: $pattern"
    rm -rf $pattern
done < ".gitignore"

echo "Cleanup complete."