"""optional continuous PCM processing; neutral controls take the direct path"""
import shutil
import subprocess
from threading import Thread


def transform_chunks(chunks, pace=1., pitch=0.):
    import numpy as np
    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Voice pace/pitch tuning needs: sudo apt install ffmpeg. Or reset pace to 1.00 and pitch to 0.00.')
    iterator = iter(chunks)
    try:
        first, rate = next(iterator)
    except StopIteration:
        return
    ratio = 2**(pitch/12)
    filters = f'asetrate={rate*ratio},aresample={rate},atempo={pace/ratio}'
    process = subprocess.Popen([executable,'-hide_banner','-loglevel','error',
        '-probesize','32','-analyzeduration','0','-f','f32le','-ar',str(rate),'-ac','1','-i','pipe:0',
        '-af',filters,'-f','f32le','-ar',str(rate),'-ac','1','-flush_packets','1','pipe:1'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    errors=[]
    def feed():
        try:
            process.stdin.write(np.asarray(first,dtype='<f4').tobytes())
            for samples, chunk_rate in iterator:
                if chunk_rate != rate:
                    raise RuntimeError('Voice changed sample rate during playback.')
                process.stdin.write(np.asarray(samples,dtype='<f4').tobytes())
        except BrokenPipeError:
            pass
        except Exception as exc:
            errors.append(exc)
        finally:
            try: process.stdin.close()
            except BrokenPipeError: pass
            # the upstream model must finish before its next generation can start
            try:
                for _ in iterator: pass
            except Exception as exc:
                errors.append(exc)
    worker=Thread(target=feed,daemon=True);worker.start()
    try:
        pending=b''
        while True:
            block=process.stdout.read(4096)
            if not block:break
            pending+=block
            end=len(pending)//4*4
            if end:
                yield np.frombuffer(pending[:end],dtype='<f4').copy(),rate
                pending=pending[end:]
        worker.join()
        if errors:raise errors[0]
        if process.wait(timeout=5) != 0:
            raise RuntimeError('ffmpeg could not apply voice tuning. Reset pace and pitch to retry.')
    finally:
        if process.poll() is None:process.terminate()
        process.stdout.close()
        worker.join()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()
