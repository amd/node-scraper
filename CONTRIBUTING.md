# Contribute to Node Scraper

AMD values and encourages contributions to our code and documentation. If you want to contribute
to our repository, first review the following guidance.

## Development workflow

Node Scraper uses GitHub to host code, collaborate, and manage version control. We use pull requests (PRs)
for all changes within our repository. We use
[GitHub issues](https://github.com/amd/node-scraper/issues) to track known issues, such as
bugs.

### Issue tracking

Before filing a new issue, search the
[existing issues](https://github.com/amd/node-scraper/issues) to make sure your issue isn't
already listed.

General issue guidelines:

* Use your best judgement for issue creation. If your issue is already listed, upvote the issue and
  comment or post to provide additional details, such as how you reproduced this issue.
* If you're not sure if your issue is the same, err on the side of caution and file your issue.
  You can add a comment to include the issue number (and link) for the similar issue. If we evaluate
  your issue as being the same as the existing issue, we'll close the duplicate.
* If your issue doesn't exist, use the issue template to file a new issue.
  * When filing an issue, be sure to provide as much information as possible, including script output so
    we can collect information about your configuration. This helps reduce the time required to
    reproduce your issue.
  * Check your issue regularly, as we may require additional information to successfully reproduce the
    issue.

### Pull requests

When you create a pull request, you should target the default branch.  Our repository uses the
**development** branch as the default integration branch.

When creating a PR, use the following process.

* Identify the issue you want to fix
* Target the default branch (usually the **development** branch) for integration
* Ensure your code builds successfully
* Do not break existing test cases
* New functionality is only merged with new unit tests
* Tests must have good code coverage
* Submit your PR and work with the reviewer or maintainer to get your PR approved
* Once approved, the PR is brought onto internal CI systems and may be merged into the component
  during our release cycle, as coordinated by the maintainer
* We'll inform you once your change is committed

> [!IMPORTANT]
> By creating a PR, you agree to allow your contribution to be licensed under the
> terms of the LICENSE.txt file.

### Pre-commit hooks

This repository uses [pre-commit](https://pre-commit.com/) to automatically format code and generate documentation. When you commit changes to plugin files, the hooks will:

1. Run code formatters (ruff, black)
2. Run type checking (mypy)
3. Automatically regenerate plugin documentation (`docs/PLUGIN_DOC.md`)

#### Setup

Install pre-commit hooks after cloning the repository:

```bash
# Activate your virtual environment
source venv/bin/activate

# Install pre-commit hooks
pre-commit install
```

#### Usage

The hooks run automatically when you commit.

```bash
# First commit attempt - hooks run and may modify files
git commit -m "Add new plugin feature"

# If hooks modified files, stage them and commit again
git add .
git commit -m "Add new plugin feature"
```

You can also run hooks manually:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run a specific hook
pre-commit run generate-plugin-docs --all-files
```

#### Plugin documentation

The `generate-plugin-docs` hook automatically regenerates `docs/PLUGIN_DOC.md` whenever plugin files in `nodescraper/plugins/inband/` are modified. This ensures the documentation stays in sync with the code.

If plugins are added or modified, the documentation will be automatically updated on the next commit.

### Documentation

Submit Node Scraper documentation changes to our
[documentation](https://github.com/amd/node-scraper/blob/development/README.md). You must update
documentation related to any new feature or API contribution.
