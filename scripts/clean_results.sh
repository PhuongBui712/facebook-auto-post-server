#!/bin/bash

# Script to delete files older than 30 days in a specified directory
# Usage: ./cleanup_old_files.sh /path/to/directory

# Check if directory path is provided
if [ $# -ne 1 ]; then
    echo "Error: Directory path is required."
    echo "Usage: $0 /path/to/directory"
    exit 1
fi

DIRECTORY="$1"

# Check if directory exists
if [ ! -d "$DIRECTORY" ]; then
    echo "Error: Directory '$DIRECTORY' does not exist."
    exit 1
fi

# Find files older than 30 days and delete them
echo "Finding and deleting files older than 30 days in '$DIRECTORY'..."
find "$DIRECTORY" -type f -mtime +30 -exec rm -f {} \;

# Optional: Count how many files were deleted
# This requires two runs of find, one before and one after deletion
# COUNT=$(find "$DIRECTORY" -type f -mtime +30 | wc -l)
# echo "Deleted $COUNT files."

echo "Cleanup complete."