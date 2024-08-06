# MyHumbleSelf

**Show your webcam image on your desktop for presentations or screencasts. (Linux only 🐧)**

<p align="center"><br>
<img alt="Tests passing" src="https://github.com/dynobo/myhumbleself/workflows/Test/badge.svg">
<a href="https://github.com/dynobo/myhumbleself/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/Code%20style-black-%23000000"></a>
<a href='https://coveralls.io/github/dynobo/myhumbleself'><img src='https://coveralls.io/repos/github/dynobo/myhumbleself/badge.svg' alt='Coverage Status' /></a>
</p>

[MyHumbleSelf in Action](https://raw.githubusercontent.com/dynobo/myhumbleself/main/resources/screenshot-02.png)

[MyHumbleSelf UI](https://raw.githubusercontent.com/dynobo/myhumbleself/main/resources/screenshot-01.png)

## Usage

✨
**[View screencast](https://raw.githubusercontent.com/dynobo/myhumbleself/main/resources/screencast.webm)**
✨

**Quickstart:**

- Start MyHumbleSelf
- Resize the window and move it to desired location
- Set to "always on top" with window manager (e.g. right click on titlebar)
- Hover the webcam image and click the "eye"-button in top right to hide window controls

**Some notable features:**

- Use face tracking to keep your head in center
- Choose among various shape-masks to add some style

## Installation

### As Flatpak

### As Python package

**Prerequisites:**

- Python 3.12+
- GTK 4.6+ and related dev packages:

  ```sh
  sudo apt-get install \
     libgirepository1.0-dev \
     libcairo2-dev \
     python3-gi \
     gobject-introspection \
     libgtk-4-dev
  ```

**Python package**

- `pipx install myhumbleself` (recommended, requires [pipx](https://pipx.pypa.io/))
- _or_ `pip install myhumbleself`

## CLI Options

```
usage: myhumbleself [-h] [-v] [-vv]

options:
  -h, --help           show this help message and exit
  -v, --verbose        Enable info logging.
  -vv, --very-verbose  Enable debug logging.
```

## Contribute

TBD

## Development Setup

**Prerequisites:**

- Python 3.12+
- `git`
- GTK 4.6+ and related dev packages:

  ```sh
  sudo apt-get install \
     libgirepository1.0-dev \
     libcairo2-dev \
     python3-gi \
     gobject-introspection \
     libgtk-4-dev
  ```

**Fork and clone**

1. [Fork](https://github.com/dynobo/myhumbleself/fork) the repository.
2. Clone to local system:
   `git clone https://github.com/<YOUR-USERNAME>/myhumbleself.git`

**Setup Virtual Environment:**

In root of repository, run:

```sh
python -m venv .venv &&
source .venv/bin/activate &&
pip install -e '.[dev]' &&
pre-commit install
```

## Design Principles

- **No network connection**<br>Everything should run locally without any network
  communication.
- **Simplicity**<br>Focus on main features. Keep UI simple. If possible, avoid text in
  the UI.
- **Dependencies**<br>The fewer dependencies, the better.

## Certification

![WOMM](https://raw.githubusercontent.com/dynobo/myhumbleself/main/resources/badge.png)
