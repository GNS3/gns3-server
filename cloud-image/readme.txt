create_image.py:

- uses fabric, which doesn't support Python 3

- prompts for Rackspace credentials if environment variables not set
  - see .novarc for example env variables
    - note that the novaclient library uses the Rackspace password and -not-
      the API key

- use '--help' for help with arguments
