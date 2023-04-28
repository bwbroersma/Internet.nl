### Debugging tests

#### Local
On test failure a video, screenshot, trace and log output regarding the failed test are placed in the `integration_tests/test-results/<test-name>` folder.

#### CI (Github Actions)
On test failure a video, screenshot, trace and log output regarding the failed test are generated. These can be downloaded as artifacts after the entire testrun has completed on the 'Summary' page of the Action Run: `https://github.com/internetstandards/Internet.nl/actions/runs/<run-id>`.
