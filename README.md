# ica_analysis_requeue_webapp
pyscript-based web app that allows a user to generate CLI and API requeue templates for Illumina Connected Analytics (ICA)

See [here](https://keneng87.pyscriptapps.com/ica-analysis-requeue/latest/) to interact with it live.

For those looking for programmatic ways to do this ---- take a look [here](https://github.com/keng404/bssh_parallel_transfer/blob/master/relaunch_pipeline.py)

## notes
- python script ```main.py``` contains logic to render elements in the ```index.html```.
- index.html is stylized by ```assets/css/examples.css```.

### todos

- [ ] create loading pages for each button press
- [ ] add more explanations of CLI/API calls used to grab information for requeue
