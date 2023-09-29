import os
from pathlib import Path
from typing import List, Optional, Dict

import agenta.config
import requests
from agenta.client.api_models import AppVariant, Image
from docker.models.images import Image as DockerImage
from requests.exceptions import RequestException

BACKEND_URL_SUFFIX = os.environ["BACKEND_URL_SUFFIX"]


class APIRequestError(Exception):
    """Exception to be raised when an API request fails."""


def get_app_by_name(app_name: str, host: str) -> str:
    """Get app by its name on the server.

    Args:
        app_name (str): Name of the app
        host (str): Hostname of the server
    """

    response = requests.get(
        f"{host}/{BACKEND_URL_SUFFIX}/apps?app_name={app_name}/",
        timeout=600,
    )
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to get app failed with status code {response.status_code} and error message: {error_message}."
        )
    return response.json()["app_id"]


def create_new_app(app_name: str, host: str) -> str:
    """Creates new app on the server.

    Args:
        app_name (str): Name of the app
        host (str): Hostname of the server
    """

    response = requests.post(
        f"{host}/{BACKEND_URL_SUFFIX}/apps/",
        json={"app_name": app_name},
        timeout=600,
    )
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to create new app failed with status code {response.status_code} and error message: {error_message}."
        )
    return response.json()["app_id"]


def add_variant_to_server(app_id: str, variant_name: str, image: Image, host: str):
    """Adds a variant to the server.

    Arguments:
        app_id: The ID of the app
        app_name -- Name of the app
        variant_name -- Name of the variant
        image_name -- Name of the image
    """
    payload = {
        "variant_name": variant_name,
        "docker_id": image.docker_id,
        "tags": image.tags,
        "base_name": None,
        "config_name": None,
    }
    response = requests.post(
        f"{host}/{BACKEND_URL_SUFFIX}/apps/{app_id}/variant/from-image/",
        json=payload,
        timeout=600,
    )
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to app_variant endpoint failed with status code {response.status_code} and error message: {error_message}."
        )
    return response.json()


def start_variant(
    variant_id: str, host: str, env_vars: Optional[Dict[str, str]] = None
) -> str:
    """
    Starts or stops a container with the given variant and exposes its endpoint.

    Args:
        variant_id (str): The ID of the variant.
        host (str): The host URL.
        env_vars (Optional[Dict[str, str]]): Optional environment variables to inject into the container.

    Returns:
        str: The endpoint of the container.

    Raises:
        APIRequestError: If the API request fails.
    """
    payload = {"action": "START"}
    if env_vars:
        payload["env_vars"] = {"env_vars": env_vars}

    try:
        response = requests.put(
            f"{host}/variants/{variant_id}/",
            json=payload,
            timeout=600,
        )

        if response.status_code != 200:
            error_message = response.json().get("detail", "Unknown error")
            raise APIRequestError(
                f"Request to start variant endpoint failed with status code {response.status_code} and error message: {error_message}."
            )
        return response.json().get("uri", "")

    except RequestException as e:
        raise APIRequestError(f"An error occurred while making the request: {e}")


def list_variants(app_id: str, host: str) -> List[AppVariant]:
    """Lists all the variants registered in the backend for an app

    Arguments:
        app_id -- the app id to which to return all the variants

    Returns:
        a list of the variants using the pydantic model
    """
    response = requests.get(
        f"{host}/{BACKEND_URL_SUFFIX}/apps/{app_id}/variants/",
        timeout=600,
    )

    # Check for successful request
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to list_variants endpoint failed with status code {response.status_code} and error message: {error_message}."
        )
    app_variants = response.json()
    return [AppVariant(**variant) for variant in app_variants]


def remove_variant(variant_id: str, host: str):
    """Removes a variant from the backend

    Arguments:
        app_name -- the app name
        variant_name -- the variant name
    """
    response = requests.delete(
        f"{host}/{BACKEND_URL_SUFFIX}/variants/{variant_id}",
        headers={"Content-Type": "application/json"},
        timeout=600,
    )

    # Check for successful request
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to remove_variant endpoint failed with status code {response.status_code} and error message: {error_message}"
        )


def update_variant_image(variant_id: str, image: Image, host: str):
    """Adds a variant to the server.

    Arguments:
        app_id: The ID of the app
        app_name -- Name of the app
        variant_name -- Name of the variant
        image_name -- Name of the image
    """
    response = requests.put(
        f"{host}/{BACKEND_URL_SUFFIX}/variants/{variant_id}/image/",
        json={"image": image.dict()},
        timeout=600,
    )
    if response.status_code != 200:
        error_message = response.json()
        raise APIRequestError(
            f"Request to update app_variant failed with status code {response.status_code} and error message: {error_message}."
        )


def send_docker_tar(app_id: str, variant_name: str, tar_path: Path, host: str) -> Image:
    with tar_path.open("rb") as tar_file:
        response = requests.post(
            f"{host}/{BACKEND_URL_SUFFIX}/containers/build_image/?app_id={app_id}&&variant_name={variant_name}",
            files={
                "tar_file": tar_file,
            },
            timeout=1200,
        )

    if response.status_code == 500:
        response_error = response.json()
        error_msg = "Serving the variant failed.\n"
        error_msg += f"Log: {response_error}\n"
        error_msg += "Here's how you may be able to solve the issue:\n"
        error_msg += "- First, make sure that the requirements.txt file has all the dependencies that you need.\n"
        error_msg += "- Second, check the Docker logs for the backend image to see the error when running the Docker container."
        raise Exception(error_msg)

    response.raise_for_status()
    image = Image.parse_obj(response.json())
    return image
