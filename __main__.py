#!/usr/bin/env python3

from fastapi import FastAPI
import uvicorn

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://localhost",
    "http://127.0.0.1:3000",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

##########################以下是zoo添加################################
import time

from kittycad.api.ml import create_text_to_cad, get_text_to_cad_model_for_user
from kittycad.client import ClientFromEnv, Client
from kittycad.models import (
    ApiCallStatus,
    Error,
    FileExportFormat,
    TextToCad,
    TextToCadCreateBody,
)

from fastapi import FastAPI, Request

    
@app.get("/text_to_cad")
async def text_to_cad(prompt: str, token: str, file_export_format: str):
    # Create our client.
    # client = ClientFromEnv()
    client = Client(token=token)
    # Prompt the API to generate a 3D model from text.
    response = create_text_to_cad.sync(
        client=client,
        # output_format=FileExportFormat.STEP,
        output_format=file_export_format,
        body=TextToCadCreateBody(
            prompt=prompt,
        ),
    )

    if isinstance(response, Error) or response is None:
        print(f"Error: {response}")
        return {
            "error":f"转换出现错误: {response}",
        }
    
    result: TextToCad = response

    # Polling to check if the task is complete
    while result.completed_at is None:
        # Wait for 5 seconds before checking again
        time.sleep(5)

        # Check the status of the task
        response = get_text_to_cad_model_for_user.sync(
            client=client,
            id=result.id,
        )

        if isinstance(response, Error) or response is None:
            print(f"Error: {response}")
            return {
                "error":f"转换出现错误: {response}",
            }

        result = response
    
    if result.status == ApiCallStatus.FAILED:
        # Print out the error message
        print(f"Text-to-CAD failed: {result.error}")
        return {
            "error":f"转换出现错误: {result.error}",
        }

    elif result.status == ApiCallStatus.COMPLETED:
        if result.outputs is None:
            print("Text-to-CAD completed but returned no files.")
            return {
                "error":f"转换出现错误，没有文件返回",
            }

        # Print out the names of the generated files
        print(f"Text-to-CAD completed and returned {len(result.outputs)} files:")
        for name in result.outputs:
            print(f"  * {name}")

        # Save the STEP data as text-to-cad-output.step
        final_result = result.outputs["source.step"]
        timestamp_ms = str(int(time.time() * 1000))
        with open(timestamp_ms + ".step", "w", encoding="utf-8") as output_file:
            output_file.write(final_result.decode("utf-8"))
            print(f"Saved output to {output_file.name}")
            
    return {
        "url":"http://localhost:5771/download?file_path=" + timestamp_ms + ".step",
    }

from fastapi.responses import FileResponse
@app.get("/download")
async def download_file(file_path):
    return FileResponse(file_path, filename=file_path, media_type="application/octet-stream")



if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=5771)