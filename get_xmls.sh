#!/bin/bash

# NOTE: Takes around 5m24s for 100k articles

source utils.sh

BASE_URL="https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/"

XML_DIR=$1
check_defined XML_DIR
rm -rf "$XML_DIR"
mkdir -p "$XML_DIR"

XML_CNT_THRESH=$2
check_defined XML_CNT_THRESH

TEMP_DIR=".temp"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

xml_cnt_cur=0
archives_list=$(curl -s "$BASE_URL" | grep -oP 'href="\K[^"]+\.tar\.gz')
for archive in $archives_list; do
    # Threshold achieved => break
    if [ $xml_cnt_cur -ge $XML_CNT_THRESH ]; then
        break
    fi

    # Download and extract the archive
    echo "Retrieving new XMLs..."
    curl -sO "$BASE_URL$archive"
    tar -xzf $archive -C $TEMP_DIR
    
    # Calculate count before moving
    xml_cnt_before=$(ls "$XML_DIR" | wc -l)
    
    # Move at most `xml_cnt_remaining` XMLs
    xml_cnt_remaining=$((XML_CNT_THRESH - xml_cnt_cur))
    find "$TEMP_DIR" -type f -name "*.xml" | head -n "$xml_cnt_remaining" | xargs -I {} mv {} "$XML_DIR/"
    
    # Calculate count after moving
    xml_cnt_after=$(ls "$XML_DIR" | wc -l)

    # Calculate the number of files moved
    xml_cnt_moved=$((xml_cnt_after - xml_cnt_before))
    xml_cnt_cur=$((xml_cnt_cur + xml_cnt_moved))

    # Print progress
    progress_percentage=$(( (xml_cnt_cur * 100) / XML_CNT_THRESH ))
    echo "Got $xml_cnt_moved new XMLs"
    echo "Progress: $xml_cnt_moved / $XML_CNT_THRESH ($progress_percentage%)"
    echo ""

    # Cleanup
    rm -rf "$TEMP_DIR/*"
    rm -f *.tar.gz
done

echo "Extracted $xml_cnt_cur XMLs into directory '$XML_DIR'"

# Cleanup
rm -rf "$TEMP_DIR"
