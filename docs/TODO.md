See the Issues board for the
[Task list](http://gitlab.com/opentasmania/oj-server/-/issues/?sort=created_date&state=opened&type%5B%5D=task&first_page_size=20)

# Big bad list of things to do

That have yet to be added to the board.

## Add validation for the most critical installer arguments

* Extensively test incorrect arguments for `kubernetes_installer.py` and produce quality errors

## Make `kubernetes_installer.py` status nicer

* Note: Irrelevant with Kubernetes approach which uses native `kubectl` tools for status

## Make renderd pre-rendered tiles configurable

## Fix example.com domain name

* Either error if it hasn't been set or if we're using developer overrides set it to the primary ethernet IP

## Check for hardcoded settings

Use a top level config.yaml for system wide kubernetes settings

## Better preseeding for debian packages (for `build-deb` action)

## External file diffs

