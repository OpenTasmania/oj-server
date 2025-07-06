See the Issues board for the
[Task list](http://gitlab.com/opentasmania/ojp-server/-/issues/?sort=created_date&state=opened&type%5B%5D=task&first_page_size=20)

# Big bad list of things to do
That have yet to be added to the board.

## Add validation for the most critical installer arguments
* Extensively test incorrect arguments and produce quality errors

## Make install.py --status nicer
* Note: Irrelevant with Kubernetes approach which uses native kubectl tools for status

## Make renderd pre-rendered tiles configurable
* Take the hardcoded logic out of the configurator and put it into config yaml

## Fix example.com domain name
* Either error if it hasn't been set or if we're using developer overrides set it to the primary ethernet IP

## Check for hardcoded settings
* Ensure that any hardcoded settings are moved to the appropriate place in the config yaml

## Better preseeding for debian packages

## Migrate state machine to sqlite db

## Configmodels should error if it can't find a setting in in config.yaml. it should propose a solution for now, however that information will eventually be contained in docstrings or similar.

## External file diffs

## Refactor installer to separate services out 
