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
python3 -m bitwarden_cli_toolkit
```

Once the GUI opens, choose a login mode, give it the URL to your bitwarden vault and the path to your bitwarden cli executable, and you're setup.

### Login modes

The login form shows which fields are required, optional or not used for the selected mode.

| Login mode | When to use | Needs |
|---|---|---|
| Password (+ authenticator MFA) | Account with a master password, with or without two step login | Username, password. If the account has two step login, a popup asks for the authenticator app code |
| API key | Automation, or when you don't want the browser / MFA | Client ID and secret of your *personal* API key (Web vault > Account settings > Security > Keys > View API key). The master password is asked later to unlock the vault |
| SSO (browser) | Accounts using single sign-on | Nothing, `bw login --sso` opens your browser. The master password is asked afterwards to unlock the vault |

API key and SSO only authenticate you, the vault is encrypted with a key derived from the master password, so the CLI needs it to unlock the vault.   
SSO accounts without a master password can only be used if the organization uses Key Connector, Trusted Device Encryption isn't supported by the Bitwarden CLI.

Only two step login with an authenticator app (TOTP) is handled by the password login mode.

### Root collections

The "Root collections" tab lets you tick one or more root (parent) collections.   
Every ticked root passes its own user and group permissions to all of its sub collections (children, grandchildren...).

### Verify

The "Verify" tab checks that every sub collection of the selected root collections holds all the user and group permissions of its root (missing permissions or different rights are reported, additional users / groups on a sub collection are only informational).   
"Fix only mismatches" then fixes just the sub collections that need it, instead of redoing the whole inheritance. The fix adds / corrects the root permissions and keeps the additional entries of the sub collection.

## API Usage

```python
from bitwarden_cli_toolkit.bwcli_wrapper import BWCli

# Login
cli = BWCli(username="some@user.tld", password="somepassword")
if cli.login_as_user():
    print("Logged in successfully.")

# Login with an account having two step login (authenticator app)
cli = BWCli(username="some@user.tld", password="somepassword")
if not cli.login_as_user() and cli.mfa_required:
    cli.set_mfa(method=0, code="123456")  # 0 = authenticator app
    cli.login_as_user()

# Login with a personal API key, the password is used to unlock the vault
cli = BWCli(username=None, password="somepassword")
cli.login_as_api(client_id="user.xxxx", client_secret="xxxx")

# Login with SSO, bw opens the browser, the password is used to unlock the vault
cli = BWCli(username=None, password="somepassword")
cli.login_as_sso()

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
Accounts with two step login (authenticator app), API key and SSO logins are supported, see [Login modes](#login-modes).   
Passwords and API secrets are handed to the bw executable through environment variables, so they don't show up in the process command line.   
Also, you can save the configuration in order to have the tool ready for action.   
The configuration file will encrypt the user password, but keep in mind that this is just a simple protection and can be workaround, especially if using the standard binaries with default encryption key.   
A good solution is to store all settings except the password.


## Compile it yourself

Fetch yourself a copy of Nuitka, and have it compiled yourself !
```
python -m nuitka  --plugin-enable=tk-inter --enable-plugin=data-hiding --python-flag=no_docstrings --python-flag=-O --standalone --output-dir=BUILDS bitwarden_cli_toolkit\bitwarden_cli_toolkit.py
```
