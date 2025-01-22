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
    FileImportFormat,
    TextToCad,
    TextToCadCreateBody,
    FileConversion
)
from typing import Dict

from kittycad.api.file import create_file_conversion
from kittycad.models.base64data import Base64Data
from kittycad.types import Unset

from fastapi import FastAPI, Request


# from pydantic import BaseModel

# class Model(BaseModel):
#     model_name: str = None

# class Msg():
#     status:int = 0
#     content:str = ''
#     description:str = ''
#     error:str = ''

@app.get("/text_to_cad")
async def text_to_cad(prompt: str, token: str, file_export_format: str, url: str):
    # Create our client.
    # client = ClientFromEnv()
    client = Client(token=token)

    # 记录开始时间
    start_time = time.time()

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
            "error": f"转换出现错误: {response}",
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
                "error": f"转换出现错误: {response}",
            }

        result = response

    if result.status == ApiCallStatus.FAILED:
        # Print out the error message
        print(f"Text-to-CAD failed: {result.error}")
        return {
            "error": f"转换出现错误: {result.error}",
        }

    elif result.status == ApiCallStatus.COMPLETED:
        if result.outputs is None:
            print("Text-to-CAD completed but returned no files.")
            return {
                "error": f"转换出现错误，没有文件返回",
            }

            # 记录结束时间并计算耗时
            end_time = time.time()
            elapsed_time = end_time - start_time  # 计算模型生成的时间
            print(f"模型生成耗时: {elapsed_time:.2f}秒")

            # 计算花费
            if elapsed_time < 10:
                # 如果耗时小于10秒，则免费
                cost = 0.0
            else:
                # 否则根据分钟数来计算费用
                # 四舍五入到最接近的分钟
                minutes = round(elapsed_time / 60)
                # 每分钟收费0.50美元
                cost = minutes * 0.50
            print(f"模型生成费用: ${cost:.2f}")

        # Print out the names of the generated files
        print(f"Text-to-CAD completed and returned {len(result.outputs)} files:")
        for name in result.outputs:
            print(f"  * {name}")

        # Save the STEP data as text-to-cad-output.step
        # final_result = result.outputs["source.step"]
        final_result = result.outputs["source." + file_export_format]
        timestamp_ms = str(int(time.time() * 1000))
        # with open(timestamp_ms + ".step", "w", encoding="utf-8") as output_file:
        with open(timestamp_ms + "." + file_export_format, "w", encoding="utf-8") as output_file:
            output_file.write(final_result.decode("utf-8"))
            print(f"Saved output to {output_file.name}")

    # 转换为fbx文件
    if file_export_format != "fbx":
        # 读取 .step 文件内容
        with open(timestamp_ms + "." + file_export_format, "rb") as file:
            step_content = file.read()

        # 转换 .step 到 .fbx
        result_fbx = create_file_conversion.sync(
            client=client,
            body=step_content,
            src_format=FileImportFormat.STEP,
            output_format=FileExportFormat.FBX,
        )

        if isinstance(result_fbx, Error) or result_fbx is None:
            return {"error": "转换 STEP 到 FBX 失败"}

        fc_fbx: FileConversion = result_fbx

        if isinstance(fc_fbx.outputs, Unset) or fc_fbx.outputs is None:
            return {"error": "FBX 转换输出为空"}

        outputs_fbx: Dict[str, Base64Data] = fc_fbx.outputs
        if len(outputs_fbx) != 1:
            return {"error": "FBX 转换输出数量不符"}

        # 保存 .fbx 文件
        fbx_file_path = timestamp_ms + ".fbx"
        for _, output in outputs_fbx.items():
            with open(fbx_file_path, "wb") as output_file:
                output_file.write(output)

    return {
        "download_url": url + "/download?file_path=" + timestamp_ms + "." + file_export_format,
        "view_url": url + "/download?file_path=" + timestamp_ms + ".fbx",
        "cost": f"模型生成费用: ${cost:.2f}"
    }


from fastapi.responses import FileResponse
@app.get("/download")
async def download_file(file_path):
    return FileResponse(file_path, filename=file_path, media_type="application/octet-stream")

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=5771)