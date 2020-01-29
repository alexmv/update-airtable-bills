#!/usr/bin/env bash

# Change into the directory of this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# Build and activate the python virtual environment if it doesn't exist
if [ ! -d "./venv" ]; then
    python3 -m venv venv
    source ./venv/bin/activate
    pip install --upgrade pip setuptools
    pip install -r requirements.txt
else
    # If it does exist, enter it
    source ./venv/bin/activate
fi

# Check for API keys
if [ ! -e "./api-keys.sh" ]; then
    echo
    echo "API keys have not been configured; you will need to have an OpenStates and an Airtable account."
    echo "You can find your Airtable API key at:   https://airtable.com/account"
    echo "You can find tour OpenStates API key at: https://openstates.org/accounts/profile/"
    echo
    echo "Once you have those, you can create a file named api-keys.sh containing them, like so:"
    echo 'AIRTABLE_API_KEY="................."'
    echo 'OPENSTATES_API_KEY="........-....-....-....-............"'
    echo
    exit 1
fi

# Load the API keys
source ./api-keys.sh
export AIRTABLE_API_KEY
export OPENSTATES_API_KEY

# Run the python
python3 ./update.py
