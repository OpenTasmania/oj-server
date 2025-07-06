See the Issues board for the
[Task list](http://gitlab.com/opentasmania/ojp-server/-/issues/?sort=created_date&state=opened&type%5B%5D=task&first_page_size=20)

# Big bad list of things to do
That have yet to be added to the board.

## Add validation for the most critical installer arguments
* Extensively test incorrect arguments and produce quality errors

## Refactor installer to be far more modular
* Further splitting is needed so that when an install of any sections are called, only the needed system packages for
  that are installed

## Add interactive arguments to installer for sections, steps and commands
* Need to leverage the exiting 'redo step' process so that we can set flags to prompt before executing any command, set
  flags to redo any specific command, etc.

## Make install.py --status nicer
* Use some sort of tree view to make `./installer.py --status` more intelligible

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

##  Move from docker to CRI-O or docker
