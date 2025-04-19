#!/bin/bash

# Run the migration script to add the instance_identifier column
echo "Running migration to add instance_identifier column to epcis_submissions table..."
python3 migrations/add_instance_identifier_column.py

# Check if migration was successful
if [ $? -eq 0 ]; then
  echo "Migration completed successfully."
  echo "You can now restart your application."
else
  echo "Migration failed! Check the logs for details."
fi