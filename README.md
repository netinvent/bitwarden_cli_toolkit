## Bitwarden CLI toolkit

So basically this was to be a toolkit, but Bitwarden admin CLI is quite limited (can't even get groups).
So it's named toolkit, but actually is just a permission inheritance tool.

## Why ?

Bitwarden works with collections and sub collections, but there is no permission inheritance between a collection and its child, so one has to manually update __all__ child collection permissions when necessary.

This tool takes the permissions from a given collection and applies them to all sub collections.

![image](https://github.com/user-attachments/assets/8300756a-3edf-4094-a12e-288e892d4150)

![image](https://github.com/user-attachments/assets/e5a41607-88b8-4da1-8d1f-07a1a2fb3ca5)

## Why so slow ?

Bitwarden CLI executable is quite slow, so be patient when execution your inheritance.

## More ?

Wrote this tool in a couple of hours just to get rid of an administration burden.  
Feel free to ask for more features, as long as bitwarden cli supports them.
