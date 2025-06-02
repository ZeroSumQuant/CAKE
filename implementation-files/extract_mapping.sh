#!/bin/bash
# Extract the Python filename from each text file

echo "File Mapping:"
echo "============="

for file in text\ *.txt; do
    if [ -f "$file" ]; then
        # Extract the first line that mentions a .py file
        pyfile=$(head -20 "$file" | grep -m1 "\.py" | grep -oE "[a-z_]+\.py" | head -1)
        if [ -n "$pyfile" ]; then
            echo "$file -> $pyfile"
        fi
    fi
done