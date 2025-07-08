## Bitwarden CLI toolkit

So basically this was to be a toolkit, but Bitwarden admin CLI is quite limited (can't even get groups).   
So it's named toolkit, but actually is just a permission inheritance tool.

## Why ?

Bitwarden works with collections and sub collections, but there is no permission inheritance between a collection and its child, so one has to manually update __all__ child collection permissions when necessary.

This tool takes the permissions from a given collection and applies them to all sub collections.

![image](https://github.com/user-attachments/assets/8300756a-3edf-4094-a12e-288e892d4150)

![image](https://github.com/user-attachments/assets/e5a41607-88b8-4da1-8d1f-07a1a2fb3ca5)

## How ?

First, you'll need a copy of the bitwarden cli executable found [here](https://bitwarden.com/download/#downloads-command-line-interface).   
On windows, just fetch the precompiled binary from the release page.   
On Linux (or windows power user), install a python interpreter and execute the following
```
python3 -m pip install -r bitwarden_api_toolkit/requirements.txt
python3 bitwarden_api_toolkit/bitwarden_api_toolkit.py
```

Once the GUI opens, give it your username, password, and URL to your bitwarden vault.   
Also give it the path to your bitwarden cli executable, and you're setup.

## Why so slow ?

Bitwarden CLI executable is quite slow when not using REST api since on every command, a full nodejs environment must be loaded. When possible, use REST api.

## More ?

Wrote this tool in a couple of hours just to get rid of an administration burden.  
Feel free to ask for more features, as long as bitwarden cli supports them.

## Compile it yourself

Fetch yourself a copy of Nuitka, and go brrrr!
```
python -m nuitka  --plugin-enable=tk-inter --enable-plugin=data-hiding --python-flag=no_docstrings --python-flag=-O --standalone --output_dir=BUILDS bitwarden_cli_toolkit\bitwarden_cli_toolkit.py
```