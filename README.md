# Simple Image Service

A super simple image service that allows you to upload images and 
get a URL to access them.

## Endpoints

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

By default, it will check for a Cloudflare Zero Access JWT. Users with the JWT
will have access to ALL endpoints.
