## Bitwarden CLI toolkit

So basically this was to be a toolkit, but Bitwarden admin CLI has some limitations (like the impossibility to get groups).   
So it's named toolkit, but actually is an API and a permission inheritance tool for collections.

## Why ?

Bitwarden works with collections and sub collections, but there is no permission inheritance between a collection and its children, so one has to manually update __all__ child collection permissions when necessary.

This tool takes the permissions from a given collection and applies them to all sub collections.

![image](https://github.com/user-attachments/assets/8300756a-3edf-4094-a12e-288e892d4150)

![image](https://github.com/user-attachments/assets/e5a41607-88b8-4da1-8d1f-07a1a2fb3ca5)

It also allows in-place update of permissions, but this should be used with care, and I'd advice to use the admin web interface to set collection permissions before having them inherited to it's children.

## How ?

First, you'll need a copy of the bitwarden cli executable found [here](https://bitwarden.com/download/#downloads-command-line-interface).   
On windows, you can fetch the precompiled binary from the release page.   
On Linux (or windows as power user), install a python interpreter and execute the following
```
python3 -m pip install -r bitwarden_cli_toolkit/requirements.txt
python3 bitwarden_cli_toolkit/bitwarden_cli_toolkit.py
```

Once the GUI opens, give it your username, password, and URL to your bitwarden vault.   
Also give it the path to your bitwarden cli executable, and you're setup.

## API Usage

```python
from bitwarden_cli_toolkit.bwcli_wrapper import BWCli

# Login
cli = BWCli(username="some@user.tld", password="somepassword")
if cli.login_as_user():
    print("Logged in successfully.")

# Get Organizations
orgs = cli.organizations()
if orgs:
    print("Organizations:", orgs)

# Search for a specific organization
orgs = cli.organizations(name="SOME_ORG")
if orgs:
    print("Organization:", orgs[0])

# Get organization details
org = cli.organization(organization_id=orgs[0]["id"])

# Search for organization collections
org_collections = cli.org_collections(organization_id=org["id"])
if org_collections:
    print("Organization collections:", collections)

# Search for a specific organization collection
org_collections = cli.org_collections(
                name="SOME COLLECTION", organization_id=org["id"]
            )
if org_collections:
    print("Collections:", collections)

# Get organization collection detail
org_collection = cli.org_collection(
                organization_id=org["id"], collection_id=org_collections[0]["id"]
                )

# Updating org_collection (nothing changed)
cli.org_collection(
    organization_id=org["id"],
    collection_id=org_collection["id"],
    data=org_collection,
                )

# Search for an item in personal vault
item = cli.list(search="SOME NAME")
if item:
    print(item)

# Search for item in organization
org_item = cli.list(search"SOME OTHER NAME", organization_id=org["id"])
if org_item:
    print(org_item)

# Logout
cli.logout()
```

## Why so slow ?

Bitwarden CLI executable is quite slow when not using REST api since on every command, a full nodejs environment must be loaded. When possible, use REST api.

## More ?

Wrote this tool in a couple of hours just to get rid of an administration burden.  
Feel free to ask for more features, as long as bitwarden cli supports them.

## Security

AFAIK, bitwarden cli tool can only login as user or via user api keys, but not via organization api keys, so we have to stick with user credentials.   
The tool will only work if user credentials aren't behind 2FA, since we can't handle 2FA at this point.   
Also, you can save the configuration in order to have the tool ready for action.   
The configuration file will encrypt the user password, but keep in mind that this is just a simple protection and can be workaround, especially if using the standard binaries with default encryption key.   
A good solution is to store all settings except the password.


## Compile it yourself

Fetch yourself a copy of Nuitka, and have it compiled yourself !
```
python -m nuitka  --plugin-enable=tk-inter --enable-plugin=data-hiding --python-flag=no_docstrings --python-flag=-O --standalone --output-dir=BUILDS bitwarden_cli_toolkit\bitwarden_cli_toolkit.py
```
