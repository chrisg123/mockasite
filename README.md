# Mockasite

> :warning: **Work in Progress**: This project is currently under development.

## Description
Record and serve back a mock version of a website. It is particularly useful to
work with a mock when using website automation tools like
[Selenium](https://www.selenium.dev) or
[Playwright](https://playwright.dev). The mock helps to avoid unnecessary
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
  

## Installation

### Prerequisites
Before installing Mockasite, ensure that you have the `build` package installed. You can install it using pip:

```sh
pip install build
```

Then run the following command in the project's root directory to install mockasite:
```sh
make install

```

## Usage

- **Capture Mode**: Use `mockasite --capture` to record and serve back a mock
  version of a website. To open the browser to a specific URL use `--url <URL>`.

- **Review Capture**: Use `mockasite --review-capture` to review the last capture.

- **Delete Capture**: Use `mockasite --delete-capture` to delete the last capture.

- **Process**: Use `mockasite --process` to process the last capture. This will
  extract and dump HTTP request and response data into a structured directory
  format.

- **Review Processed**: Use `mockasite --review-processed` to review processed files.

- **Delete Processed**: Use `mockasite --delete-processed` to delete processed files.


- **Playback Mode**: Use `mockasite --playback` to replay processed data as a
  functioning interactive mock of the original site.

- **Export Functionality**: Use `mockasite --export` to export a standalone server
  that serves the mock website.

## Licence

Mockasite is released under the MIT License. See the [LICENSE](LICENSE) file for
more details.
