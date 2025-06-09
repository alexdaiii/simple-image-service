# Simple Image Service

A super simple image service that allows you to upload images and 
get a URL to access them. Requires Cloudflare Zero Trust for Authentication
+ Authorization and some S3 compatible storage for storing the images.

## API Endpoints

Has 2 endpoints:

1. POST: /image - Upload an image

   - Body: (json) with this format:
   
        ```json
        {
          "image": "base_64_encoded_image_string",
          "project": "string",
          "key": "string"
        }
        ```
   - Returns: (json) with this format:
   
        ```json
        {
          "url": "https://example.com/",
          "width": 0,
          "height": 0,
          "size": 0
        }
        ```
   - It will determine the mime type of the image (avaliable types: png, jpeg, webp, avif) 
     and store it in a specified s3 compatible storage at `s3://<project>/<key>.<format>`.

2. GET: /image/{project}/{key} - Get an image

   - Returns: (image) the image stored at `s3://<project>/<key>.<format>`.
   - Query Parameters:
     - width: (int | None) The width of the image to return. If not specified, the original width is returned.
     - height: (int | None) The height of the image to return. If not specified, the original height is returned.
   - The image will be resized to the specified width and height and maintain the original aspect ratio.

## Authentication

By default, it will check for a Cloudflare Zero Access JWT. Users (emails) listed
in the `/config/post_allowlist.json` file will be allowed to upload images.
The emails from the JWT will be checked against this list.

## How to run

This uses Docker compose to run the service. 

```shell
docker compose up -d
```

### Environment Variables

- AWS_S3_BUCKET: The S3 bucket to store the images in.
- POLICY_AUD: The application in Cloudflare Zero Trust that is used for authentication.
- TEAM_DOMAIN: The domain of the Cloudflare Zero Trust team.
- TUNNEL_TOKEN: The token for the Cloudflare Tunnel to access the service.

Optional values:

- AWS_ACCESS_KEY_ID: For boto3
- AWS_SECRET_ACCESS_KEY: For boto3
- AWS_DEFAULT_REGION: For boto3
- AWS_PROFILE_NAME: If using aws cli, then set this to the profile name to use.
- ALLOWED_ORIGINS: A comma separated list of allowed origins for CORS. If not provided, will only allow same origin requests.
- ALLOWED_ORIGINS_REGEX: A regex pattern to match allowed origins for CORS.
- PYJWK_CACHE_LIFESPAN: The cache lifespan for the JWKs used for Cloudflare Zero Trust authentication. Default is 14400 seconds (4 hours).
- ALLOWLIST_FILE: The path to the allowlist file. Default is `/config/post_allowlist.json`.
- DB_FILE: The path to the SQLite database file. Default is `/data/images.sqlite`.
- MAX_FILE_SIZE: The maximum file size for uploaded images in bytes. Default is 5MB
- HOST: The hostname of the service (must include the protocol). Used to generate URLs when uploading images.
- LOG_LEVEL: The log level for the service. Default is `ERROR`. Options are `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
