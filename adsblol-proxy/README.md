# ADSB.lol Proxy API
The enclosed `adsblol_proxy.py` file was developed to be deployed using an [AWS Lambda](https://aws.amazon.com/lambda/) behind an [AWS API Gateway](https://aws.amazon.com/api-gateway/). For the default Skyportal configuration this should fall well within the monthly limits of the AWS Free Tier.

If, like me, you've never used AWS before this point, the following steps should help you get up and running. If you know what you're doing then you can probably figure all this out without my help.

## AWS Lambda
### Create Function
From the Lambda console, create a new function with the following configuration:
  * Author from scratch
  * Whatever function name you want
  * Python 3.11 Runtime
  * x86_64 architecture

Once created, edit your Runtime Settings and change the Handler to `adsblol_proxy.lambda_handler`.

### Create a `.zip` deployment
Our Lambda depends on [`httpx`](https://github.com/encode/httpx/) to make its web request, so it will need to be installed along with its dependencies before we can deploy. One way to achieve this with Lambda is to upload a [`.zip` deployment package](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies); the documentation can be a little obtuse but ultimately the goal is to end up with a zip file whose contents look something like this:

```
anyio/
anyio-4.0.0.dist-info/
certifi/
certifi-2023.7.22.dist-info/
h11/
h11-0.14.0.dist-info/
httpcore/
httpcore-1.0.2.dist-info/
httpx/
httpx-0.25.1.dist-info/
idna/
idna-3.4.dist-info/
sniffio/
sniffio-1.3.0.dist-info/
adsblol_proxy.py
```

I accomplished this using a virtual environment, e.g.:

```
$ python -m venv ./.venv
$ source ./.venv/Scripts/activate
$ python -m pip install -U pip httpx
```

Move or copy the everything from `./.venv/Lib/site-packages` **EXCEPT** `pip` (blows up the file size unnecessarily & we don't need it) into the directory with `adsblol_proxy.py` and zip everything together so you get the layout above. You can then upload this zip file to Lambda & then deploy the code.

## AWS API Gateway
### Create API
From the API Gateway console, create a new API:
  * REST API
  * New API
  * Whatever name you'd like
  * Optional description
  * Regional endpoint type

### Create Method
Under resources, create a new method:
  * `GET` method type
  * Lambda function integration type
  * Enable "Lambda proxy integration"
  * If you've already created your Lambda function above, you should be able to select it
  * Default timeout should be fine

### Edit Method
Edit your method request settings:
  * Authorization - None
  * Request validator - None
  * API key required - CHECK
  * URL query string parameters
    * `lat`, required
    * `lon`, required
    * `radius`, required

Once this is done, Deploy your API. You will need to specify a stage name if you haven't previously. Since you're just doing a hobby API you can name it whatever you want; I called mine `live`.

Make a note of your Invoke URL, which can be found under Stages. It will be something like `https://abcd123.execute-api.us-east-69.amazonaws.com/live/`.

### Create an API key
Under API Keys create a new API key & store in a secure location that you can access later.

### Create a Usage Plan
This must be created in order for the API key to work. Fill out the options however you'd like.

Once this is created you'll need to add a stage, this is what you targeted when you deployed your API.

Finally, you'll need to add your API key to the Associated API keys.

## Testing
You can check that your API is functional using `curl`:

```
$ curl --location "https://abcd123.execute-api.us-east-69.amazonaws.com/live/?lat=42.41&lon=-71.17&radius=30" --header "x-api-key:<key>"
```

Which should give back some aircraft data.

## Configuring Skyportal
To utilize the proxy server, copy your Invoke URL and API key into `secrets.py`, and set `AIRCRAFT_DATA_SOURCE = "proxy"` in your `skyportal_config.py`.
