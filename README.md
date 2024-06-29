# MyHumbleSelf

**_Utility to display webcam image for presentation or screencasts on Linux._**

<p align="center"><br>
<img alt="Tests passing" src="https://github.com/dynobo/my-humble-self/workflows/Test/badge.svg">
<a href="https://github.com/dynobo/my-humble-self/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/Code%20style-black-%23000000"></a>
<a href='https://coveralls.io/github/dynobo/my-humble-self'><img src='https://coveralls.io/repos/github/dynobo/my-humble-self/badge.svg' alt='Coverage Status' /></a>
</p>

![MyHumbleSelf Screenshot](TBD)

## Prerequisites

- Python 3.12+
- GTK 4.6+ (shipped since Ubuntu 22.04) + related dev packages:
  ```sh
  sudo apt-get install \
     libgirepository1.0-dev \
     libcairo2-dev \
     python3-gi \
     gobject-introspection \
     libgtk-4-dev
  ```

## Installation

- `pipx install myhumbleself` (recommended, requires [pipx](https://pipx.pypa.io/))
- _or_ `pip install myhumbleself`

## Usage

TBD

## CLI Options

TBD

## Contribute

TBD

## Design Principles

- **No network connection**<br>Everything should run locally without any network
  communication.
- **Dependencies**<br>The fewer dependencies, the better.

## Certification

![WOMM](https://raw.githubusercontent.com/dynobo/my-humble-self/main/badge.png)
