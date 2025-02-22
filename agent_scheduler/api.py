import io
import os
import json
from fastapi import File, HTTPException, UploadFile
import requests
import threading
from uuid import uuid4
from zipfile import ZipFile
from pathlib import Path
from typing import Optional, Dict
from gradio.routes import App
from PIL import Image
from fastapi.responses import StreamingResponse, FileResponse

import numpy as np
from modules import shared, progress

from .db import Task, TaskStatus, task_manager
from .models import (
    Txt2ImgApiTaskArgs,
    Img2ImgApiTaskArgs,
    QueueTaskResponse,
    QueueStatusResponse,
    HistoryResponse,
    TaskModel,
    UpdateTaskArgs,
)
from .task_runner import TaskRunner
from .helpers import log, request_with_retry
from .task_helpers import encode_image_to_base64, img2img_image_args_by_mode


def api_callback(callback_url: str, task_id: str, status: TaskStatus, images: list):
    files = []
    for img in images:
        img_path = Path(img)
        ext = img_path.suffix.lower()
        content_type = f"image/{ext[1:]}"
        files.append(
            (
                "files",
                (img_path.name, open(os.path.abspath(img), "rb"), content_type),
            )
        )

    return requests.post(
        callback_url,
        timeout=5,
        data={"task_id": task_id, "status": status.value},
        files=files,
    )


def on_task_finished(
    task_id: str,
    task: Task,
    status: TaskStatus = None,
    result: dict = None,
    **_,
):
    # handle api task callback
    if not task.api_task_callback:
        return

    upload = lambda: api_callback(
        task.api_task_callback,
        task_id=task_id,
        status=status,
        images=result["images"],
    )

    request_with_retry(upload)


def regsiter_apis(app: App, task_runner: TaskRunner):
    log.info("[AgentScheduler] Registering APIs")


    @app.post("/agent-scheduler/v1/queue/t2i_roop_file", response_model=QueueTaskResponse)
    async def t2i_roop_file(file: UploadFile = File()):
        task_id = str(uuid4())
        checkpoint = "majicmixRealistic_v6.safetensors [e4a30e4607]"
        #callback_url = args.pop("callback_url", None)
        callback_url = None
        try:
            img_file = file.file
            # 将文件转换为
            im = Image.open(img_file).convert("RGB")
            img_array = np.array(im)
            
            w, h, d = img_array.shape
            mask_array = np.full((w, h, 4), [0, 0, 0, 255], np.uint8)

            named_args = {
                    'prompt': '(photo-realistic:1.3),(hyperdetailed:1.2),best quality,realistic,photograph,1girl,full body,cute & girly (idolmaster),outdoors,sunlight,magazine scan,wearing glasses, smile,\n',
                    'negative_prompt': 'ng_deepnegative_v1_75t, (badhandv4:1.3), (worst quality:2), (low quality:2), (normal quality:2),lowres, bad anatomy, bad hands, ((monochrome)), ((grayscale)) ,watermark',
                    'prompt_styles': [],
                    'steps': 30,
                    'sampler_index': 17,
                    'restore_faces': False,
                    'tiling': False,
                    'n_iter': 1,
                    'batch_size': 1,
                    'cfg_scale': 7,
                    'seed': -1.0,
                    'subseed': -1.0,
                    'subseed_strength': 0,
                    'seed_resize_from_h': 0,
                    'seed_resize_from_w': 0,
                    'seed_enable_extras': False,
                    'height': 1024,
                    'width': 768,
                    'enable_hr': False,
                    'denoising_strength': 0.7,
                    'hr_scale': 2,
                    'hr_upscaler': 'Latent',
                    'hr_second_pass_steps': 0,
                    'hr_resize_x': 0,
                    'hr_resize_y': 0,
                    'hr_sampler_index': 0,
                    'hr_prompt': '',
                    'hr_negative_prompt': '',
                    'override_settings_texts': ['Clip skip: 1'],
                    'request': {'username': None},
                    'sampler_name': 'DPM++ SDE Karras'
                    }
            
            unet0_args = {'is_cnet': True,
                'enabled': True,
                'module': 'openpose_face',
                'model': 'control_v11p_sd15_openpose_fp16 [73c2b67d]',
                'weight': 1,
                'image': {'image': img_array, 'mask': mask_array},
                'resize_mode': 'Crop and Resize',
                'low_vram': False,
                'processor_res': 512,
                'threshold_a': -1,
                'threshold_b': -1,
                'guidance_start': 0,
                'guidance_end': 1,
                'pixel_perfect': True,
                'control_mode': 'Balanced',
                'is_ui': True,
                'input_mode': 'simple',
                'batch_images': '',
                'output_dir': '',
                'loopback': False}
            
            unet1_args = {
                'is_cnet': True,
                'enabled': False,
                'module': 'none',
                'model': 'None',
                'weight': 1.0,
                'image': None,
                'resize_mode': 'Crop and Resize',
                'low_vram': False,
                'processor_res': -1,
                'threshold_a': -1,
                'threshold_b': -1,
                'guidance_start': 0.0,
                'guidance_end': 1.0,
                'pixel_perfect': False,
                'control_mode': 'Balanced',
                'is_ui': True,
                'input_mode': 'simple',
                'batch_images': None,
                'output_dir': '',
                'loopback': False
                }
            
            params = json.dumps(
                {
                    "args": named_args,
                    "checkpoint": checkpoint,
                    "is_ui": True,
                    "is_img2img": False,
                }
            )
            script_args = [0,
                False,
                {},
                {},
                False,
                True,
                False,
                0,
                -1,
                False,
                '',
                0,
                im , # 这里是roop的PIL Image
                True,
                '0',
                '/home/ubuntu/stable-diffusion-webui/models/roop/inswapper_128.onnx',
                'GFPGAN',
                1,
                'R-ESRGAN 4x+',
                1,
                1,
                False,
                True,
                True,
                False,
                1,
                False,
                False,
                False,
                1.1,
                1.5,
                100,
                0.7,
                False,
                False,
                True,
                False,
                False,
                0,
                'Gustavosta/MagicPrompt-Stable-Diffusion',
                '',
                False,
                False,
                'LoRA',
                'None',
                0,
                0,
                'LoRA',
                'None',
                0,
                0,
                'LoRA',
                'None',
                0,
                0,
                'LoRA',
                'None',
                0,
                0,
                'LoRA',
                'None',
                0,
                0,
                None,
                'Refresh models']
            
            # 添加controlnet
            script_args.extend([unet0_args, unet1_args, unet1_args])

            script_args.extend([False, False, 0, None, [], 0, False, [], [], False, 0, 1, False, False, 0, None, [], -2, False, [], False, 0, None, None, False, '1:1,1:2,1:2', '0:0,0:0,0:1', '0.2,0.8,0.8', 150, 0.2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, False, False, 'positive', 'comma', 0, False, False, '', 1, '', [], 0, '', [], 0, '', [], True, False, False, False, 0, None, None, False, None, None, False, None, None, False, 50])
            
            task = task_runner.register_ui_task_raw(
                task_id,
                is_img2img=False,
                params=params,
                script_args=script_args,
            )
            if callback_url:
                task.api_task_callback = callback_url
                task_manager.update_task(task)

            task_runner.execute_pending_tasks_threading()

            return QueueTaskResponse(task_id=task_id)
            # im.save('cherry_0730.jpg', 'JPEG', quality=50) 
            # return 'got it'
        except Exception:
            raise HTTPException(status_code=500, detail='Something went wrong')
        finally:
            file.file.close()
            im.close()

    @app.post("/agent-scheduler/v1/queue/t2i_roop", response_model=QueueTaskResponse)
    def queue_t2i_roop(body: Txt2ImgApiTaskArgs):
        task_id = str(uuid4())
        args = body.dict()
        checkpoint = "majicmixRealistic_v6.safetensors [e4a30e4607]"
        #callback_url = args.pop("callback_url", None)
        callback_url = None
        task = task_runner.register_ui_task(
            task_id,
            is_img2img=False,
            args=args,
            checkpoint=checkpoint,
            request=None
        )
        if callback_url:
            task.api_task_callback = callback_url
            task_manager.update_task(task)

        task_runner.execute_pending_tasks_threading()

        return QueueTaskResponse(task_id=task_id)

    @app.post("/agent-scheduler/v1/queue/txt2img", response_model=QueueTaskResponse)
    def queue_txt2img(body: Txt2ImgApiTaskArgs):
        task_id = str(uuid4())
        args = body.dict()
        checkpoint = args.pop("checkpoint", None)
        callback_url = args.pop("callback_url", None)
        task = task_runner.register_api_task(
            task_id,
            api_task_id=None,
            is_img2img=False,
            args=args,
            checkpoint=checkpoint,
        )
        if callback_url:
            task.api_task_callback = callback_url
            task_manager.update_task(task)

        task_runner.execute_pending_tasks_threading()

        return QueueTaskResponse(task_id=task_id)

    @app.post("/agent-scheduler/v1/queue/img2img", response_model=QueueTaskResponse)
    def queue_img2img(body: Img2ImgApiTaskArgs):
        task_id = str(uuid4())
        args = body.dict()
        checkpoint = args.pop("checkpoint", None)
        callback_url = args.pop("callback_url", None)
        task = task_runner.register_api_task(
            task_id,
            api_task_id=None,
            is_img2img=True,
            args=args,
            checkpoint=checkpoint,
        )
        if callback_url:
            task.api_task_callback = callback_url
            task_manager.update_task(task)

        task_runner.execute_pending_tasks_threading()

        return QueueTaskResponse(task_id=task_id)

    def format_task_args(task):
        task_args = TaskRunner.instance.parse_task_args(task, deserialization=False)
        named_args = task_args.named_args
        named_args["checkpoint"] = task_args.checkpoint
        # remove unused args to reduce payload size
        named_args.pop("alwayson_scripts", None)
        named_args.pop("script_args", None)
        named_args.pop("init_images", None)
        for image_args in img2img_image_args_by_mode.values():
            for keys in image_args:
                named_args.pop(keys[0], None)
        return named_args

    @app.get("/agent-scheduler/v1/queue", response_model=QueueStatusResponse)
    def queue_status_api(limit: int = 20, offset: int = 0):
        current_task_id = progress.current_task
        total_pending_tasks = task_manager.count_tasks(status="pending")
        pending_tasks = task_manager.get_tasks(
            status=TaskStatus.PENDING, limit=limit, offset=offset
        )
        parsed_tasks = []
        for task in pending_tasks:
            params = format_task_args(task)
            task_data = task.dict()
            task_data["params"] = params
            if task.id == current_task_id:
                task_data["status"] = "running"

            parsed_tasks.append(TaskModel(**task_data))

        return QueueStatusResponse(
            current_task_id=current_task_id,
            pending_tasks=parsed_tasks,
            total_pending_tasks=total_pending_tasks,
            paused=TaskRunner.instance.paused,
        )

    @app.get("/agent-scheduler/v1/history", response_model=HistoryResponse)
    def history_api(status: str = None, limit: int = 20, offset: int = 0):
        bookmarked = True if status == "bookmarked" else None
        if not status or status == "all" or bookmarked:
            status = [
                TaskStatus.DONE,
                TaskStatus.FAILED,
                TaskStatus.INTERRUPTED,
            ]

        total = task_manager.count_tasks(status=status)
        tasks = task_manager.get_tasks(
            status=status,
            bookmarked=bookmarked,
            limit=limit,
            offset=offset,
            order="desc",
        )
        parsed_tasks = []
        for task in tasks:
            params = format_task_args(task)
            task_data = task.dict()
            task_data["params"] = params
            parsed_tasks.append(TaskModel(**task_data))

        return HistoryResponse(
            total=total,
            tasks=parsed_tasks,
        )

    @app.get("/agent-scheduler/v1/task/{id}")
    def get_task(id: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        params = format_task_args(task)
        task_data = task.dict()
        task_data["params"] = params
        if task.id == progress.current_task:
            task_data["status"] = "running"

        return {"success": True, "data": TaskModel(**task_data)}

    @app.put("/agent-scheduler/v1/task/{id}")
    def update_task(id: str, body: UpdateTaskArgs):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        should_save = False
        if body.name is not None:
            task.name = body.name
            should_save = True

        if body.checkpoint or body.params:
            params: Dict = json.loads(task.params)
            if body.checkpoint is not None:
                params["checkpoint"] = body.checkpoint
            if body.checkpoint is not None:
                params["args"].update(body.params)

            task.params = json.dumps(params)
            should_save = True

        if should_save:
            task_manager.update_task(task)

        return {"success": True, "message": "Task updated."}

    @app.post("/agent-scheduler/v1/run/{id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/run")
    def run_task(id: str):
        if progress.current_task is not None:
            if progress.current_task == id:
                return {"success": False, "message": "Task is running"}
            else:
                # move task up in queue
                task_manager.prioritize_task(id, 0)
                return {
                    "success": True,
                    "message": "Task is scheduled to run next",
                }
        else:
            # run task
            task = task_manager.get_task(id)
            current_thread = threading.Thread(
                target=TaskRunner.instance.execute_task,
                args=(
                    task,
                    lambda: None,
                ),
            )
            current_thread.daemon = True
            current_thread.start()

            return {"success": True, "message": "Task is executing"}

    @app.post("/agent-scheduler/v1/requeue/{id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/requeue")
    def requeue_task(id: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        task.id = str(uuid4())
        task.result = None
        task.status = TaskStatus.PENDING
        task.bookmarked = False
        task.name = f"Copy of {task.name}" if task.name else None
        task_manager.add_task(task)
        task_runner.execute_pending_tasks_threading()

        return {"success": True, "message": "Task requeued"}

    @app.post("/agent-scheduler/v1/delete/{id}", deprecated=True)
    @app.delete("/agent-scheduler/v1/task/{id}")
    def delete_task(id: str):
        if progress.current_task == id:
            shared.state.interrupt()
            task_runner.interrupted = id
            return {"success": True, "message": "Task interrupted"}

        task_manager.delete_task(id)
        return {"success": True, "message": "Task deleted"}

    @app.post("/agent-scheduler/v1/move/{id}/{over_id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/move/{over_id}")
    def move_task(id: str, over_id: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        if over_id == "top":
            task_manager.prioritize_task(id, 0)
            return {"success": True, "message": "Task moved to top"}
        elif over_id == "bottom":
            task_manager.prioritize_task(id, -1)
            return {"success": True, "message": "Task moved to bottom"}
        else:
            over_task = task_manager.get_task(over_id)
            if over_task is None:
                return {"success": False, "message": "Task not found"}

            task_manager.prioritize_task(id, over_task.priority)
            return {"success": True, "message": "Task moved"}

    @app.post("/agent-scheduler/v1/bookmark/{id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/bookmark")
    def pin_task(id: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        task.bookmarked = True
        task_manager.update_task(task)
        return {"success": True, "message": "Task bookmarked"}

    @app.post("/agent-scheduler/v1/unbookmark/{id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/unbookmark")
    def unpin_task(id: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        task.bookmarked = False
        task_manager.update_task(task)
        return {"success": True, "message": "Task unbookmarked"}

    @app.post("/agent-scheduler/v1/rename/{id}", deprecated=True)
    @app.post("/agent-scheduler/v1/task/{id}/rename")
    def rename_task(id: str, name: str):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        task.name = name
        task_manager.update_task(task)
        return {"success": True, "message": "Task renamed."}

    @app.get("/agent-scheduler/v1/results/{id}", deprecated=True)
    @app.get("/agent-scheduler/v1/task/{id}/results")
    def get_task_results(id: str, zip: Optional[bool] = False):
        task = task_manager.get_task(id)
        if task is None:
            return {"success": False, "message": "Task not found"}

        if task.status != TaskStatus.DONE:
            return {"success": False, "message": f"Task is {task.status}"}

        if task.result is None:
            return {"success": False, "message": "Task result is not available"}

        result: dict = json.loads(task.result)
        infotexts = result["infotexts"]

        if zip:
            zip_buffer = io.BytesIO()

            # Create a new zip file in the in-memory buffer
            with ZipFile(zip_buffer, "w") as zip_file:
                # Loop through the files in the directory and add them to the zip file
                for image in result["images"]:
                    if Path(image).is_file():
                        zip_file.write(Path(image), Path(image).name)

            # Reset the buffer position to the beginning to avoid truncation issues
            zip_buffer.seek(0)

            # Return the in-memory buffer as a streaming response with the appropriate headers
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=results-{id}.zip"
                },
            )
        else:
            data = [
                {
                    "image": encode_image_to_base64(Image.open(image)),
                    "infotext": infotexts[i],
                }
                for i, image in enumerate(result["images"])
                if Path(image).is_file()
            ]

            return {"success": True, "data": data}

    @app.post("/agent-scheduler/v1/pause", deprecated=True)
    @app.post("/agent-scheduler/v1/queue/pause")
    def pause_queue():
        shared.opts.queue_paused = True
        return {"success": True, "message": "Queue paused."}

    @app.post("/agent-scheduler/v1/resume", deprecated=True)
    @app.post("/agent-scheduler/v1/queue/resume")
    def resume_queue():
        shared.opts.queue_paused = False
        TaskRunner.instance.execute_pending_tasks_threading()
        return {"success": True, "message": "Queue resumed."}

    @app.post("/agent-scheduler/v1/queue/clear")
    def clear_queue():
        task_manager.delete_tasks(status=TaskStatus.PENDING)
        return {"success": True, "message": "Queue cleared."}

    @app.post("/agent-scheduler/v1/history/clear")
    def clear_history():
        task_manager.delete_tasks(
            status=[
                TaskStatus.DONE,
                TaskStatus.FAILED,
                TaskStatus.INTERRUPTED,
            ]
        )
        return {"success": True, "message": "History cleared."}

    task_runner.on_task_finished(on_task_finished)
