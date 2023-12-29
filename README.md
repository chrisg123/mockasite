# Mockasite

> :warning: **Work in Progress**: This project is currently under development.

## Description
Record and serve back a mock version of a website. It is particularly useful to
work with a mock when using website automation tools like
[Selenium](https://www.selenium.dev). The mock helps to avoid unnecessary
interactions with a website's actual servers during development and testing
phases.


## Key Features

- **Traffic Capture**: Records web interactions for later use, capturing the
  dynamic behavior of the site.
  
- **Mock Server**: Replays captured data, offering a functioning interactive
  mock of the original website running in a browser for testing and
  development purposes.
  
- **Export Standalone Server**: Provides the capability to export a standalone
  server setup. This is ideal for integrating the mock website into other
  projects or for isolated testing environments.
  
  
## Usage

- **Capture Mode**: `mockasite --capture`

- **Playback Mode**: `mockasite --playback`

- **Export Functionality**: `mockasite --export`

## Licence

Mockasite is released under the MIT License. See the [LICENSE](LICENSE) file for
more details.
