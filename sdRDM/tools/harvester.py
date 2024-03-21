import rich
import instructor
from openai import OpenAI


def harvest_metadata(
    model: "DataModel",
    data: str,
    openai_key: str,
    prompt: str = "Extract metadata from the following document",
    gpt_model: str = "gpt-4",
    **openai_kwargs,
) -> "DataModel":
    """
    Harvests metadata from a document using OpenAI GPT-4 model and adds it to the given data model.

    Args:
        model (DataModel): The data model instance.
        data (str): The document from which to extract metadata.
        openai_key (str): The API key for OpenAI.
        prompt (str, optional): The prompt for the OpenAI chat completion. Defaults to "Extract metadata from the following document".
        gpt_model (str, optional): The GPT model to use. Defaults to "gpt-4".
        **openai_kwargs: Additional keyword arguments to pass to the OpenAI API.

    Returns:
        DataModel: The updated data model instance with extracted metadata.
    """

    assert hasattr(model, "model_fields"), "'model' must be an instance of DataModel"

    rich.print(f"[bold]\n\n👨‍🌾 Harvesting metadata from text into {model.__name__}")

    client = instructor.patch(
        OpenAI(
            api_key=openai_key,
            **openai_kwargs,
        )
    )

    result = client.chat.completions.create(
        model=gpt_model,
        response_model=model,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}: {data}",
            },
        ],
    )

    rich.print(f"[bold]\n\nMetadata harvested successfully!\n")

    return result
