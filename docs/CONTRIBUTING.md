# Contribution Guidelines for Open Journey Server

We welcome and appreciate contributions to the "Open Journey Server" project! Your help can make this
project even better.

## How to Contribute

This project is hosted on [GitLab](https://gitlab.com/opentasmania/oj-server). We utilize GitLab's features for
collaboration and issue tracking.

### 1. Reporting Issues

If you find a bug, have a feature request, or notice any unexpected behavior, please report it on
our [Issues board](https://gitlab.com/opentasmania/oj-server/issues).

When reporting an issue, please provide as much detail as possible, including:

* A clear and concise description of the problem.
* Steps to reproduce the issue.
* Expected behavior.
* Actual behavior.
* Any relevant error messages or logs.
* Your operating system and environment details.

### 2. Suggesting Enhancements

If you have an idea for a new feature or an improvement to existing functionality, you can also propose it on
the [Issues board](https://gitlab.com/opentasmania/oj-server/issues). Please describe your suggestion clearly and
explain its benefits.

### 3. Submitting Code Contributions

We encourage code contributions! If you'd like to contribute code, please follow these steps:

1. **Fork the repository:** Create your own fork of the project on GitLab.
2. **Clone your fork:**
   ```bash
   git clone https://gitlab.com/<your-username>/oj-server.git
   cd oj-server
   ```
3. **Create a new branch:** For each new feature or bug fix, create a separate branch. Use a descriptive name for your
   branch (e.g., `feature/add-transxchange`, `bugfix/fix-osrm-docker`).
   ```bash
   git checkout -b your-branch-name
   ```
4. **Make your changes:** Implement your feature or fix the bug.
5. **Test your changes:** Ensure your changes work as expected and don't introduce new issues.
6. **Commit your changes:** Write clear and concise commit messages.
   ```bash
   git commit -m "feat: Add optimised GTFS processing"
   ```
   (Using conventional commits is preferred, but not strictly enforced for initial contributions.)
7. **Push your branch to your fork:**
   ```bash
   git push origin your-branch-name
   ```
8. **Create a Merge Request (MR):** Go to your fork on GitLab and create a new Merge Request targeting the `main` branch
   of the original repository.
    * Provide a clear title and description for your MR.
    * Reference any relevant issues.
    * Explain the changes you've made and why.

### 4. Code Style and Quality

* **Python Code:** Please adhere to PEP 8 guidelines for Python code.
* **Documentation:** If you add new features, please update relevant documentation (e.g., `README.md`, comments in
  code).
* **Testing:** If possible, include unit tests for new functionality.

For more detailed information about the development environment, testing, and code style, please refer to the [Developer Guidelines](DEVELOPERS.md) file.

## Contact

For any questions regarding contributions, please feel free to reach out to the primary
maintainer: [Peter Lawler (relwalretep@gmail.com)](mailto:relwalretep@gmail.com).

Thank you for your interest in contributing to this project!
