# Retainer

A simple script designed for CI with Portainer.

## Configure in your project

Technically you can use this script in any kind of deploy scenario. This script is specially designed to work with Swarm services.

### GitLab CI

Add some variables to your CI/CD configurations:

- `PORTAINER_URL`: **(required)** your Portainer address.
- `PORTAINER_USERNAME`: **(required)** a valid Portainer user.
- `PORTAINER_PASSWORD`: **(required)** the password for Portainer user.
- `PORTAINER_NODES`: (optional) a comma-separated list of Docker nodes, or an asterisk (*) for all nodes, or you can omit this variable and the script will pull the image in the default node.
- `PORTAINER_ENDPOINT`: (optional) the target Portainer endpoint, or you can omit this variable and the script will choose the first endpoint available.
- `PYTHONUNBUFFERED`: (optional) set any value for this variable to disable stdout and stderr buffering on Python.

Also, you need to embed the script as a file in your CI/CD configuration. Add a variable called `RETAINER`, select the "File" type and paste [the Retainer script](https://raw.githubusercontent.com/timoteoramos/retainer/master/src/retainer.py) in the content field.

After that, you can use this example as a CI configuration:

```yaml
stages:
  - build
  - deploy

# Build
build_image:
  only:
    - master
  image: docker:latest
  stage: build
  services:
    - docker:dind
  script:
    - export TAG=$(if [ $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH ]; then echo 'latest'; else echo $CI_COMMIT_BRANCH; fi)
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker pull $CI_REGISTRY_IMAGE:$TAG
    - docker build -t $CI_REGISTRY_IMAGE:$TAG .
    - docker push $CI_REGISTRY_IMAGE:$TAG

# Deploy
portainer:
  only:
    - master
  image: alpine:latest
  stage: deploy
  script:
    - export TAG=$(if [ $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH ]; then echo 'latest'; else echo $CI_COMMIT_BRANCH; fi)
    - apk add py3-requests
    - python3 $RETAINER --image $CI_REGISTRY_IMAGE:$TAG
```

With this configuration, the CI will use some predefined variables of your project, build a default Dockerfile in the root of your project, and then deploy it on your Portainer.
