package com.yaheen.fayconnectordemo;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.Manifest;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.MediaPlayer;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import com.google.android.material.snackbar.Snackbar;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.net.SocketException;
import java.util.Arrays;
import java.util.Date;

public class MainActivity extends AppCompatActivity {
    private TextView tv = null;
    private AudioRecord record;
    private int recordBufsize = 0;
    private Socket socket = null;
    private InputStream in = null;
    private OutputStream out = null;
    private Thread sendThread = null;
    private Thread receThread = null;
    private boolean running = false;
    private File cacheDir = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        this.cacheDir = getCacheDir();
        tv = this.findViewById(R.id.tv);
        tv.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                Log.d("fay","onclick");
                running = !running;
                sendThread = new Thread(new Runnable() {
                    @Override
                    public void run() {
                        if (!running){//关闭
                            running = false;
                            return;

                        }
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                            if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                                if (ActivityCompat.shouldShowRequestPermissionRationale(MainActivity.this, Manifest.permission.RECORD_AUDIO)) {
                                    Log.d("fay","用户彻底拒绝了权限");
                                    return;
                                } else {
                                    //  用户未彻底拒绝授予权限
                                    ActivityCompat.requestPermissions(MainActivity.this, new String[]{Manifest.permission.RECORD_AUDIO}, 1);
                                }
                            }

                            if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                                Log.d("fay","权限ok");
                                if (record == null){
                                    recordBufsize = AudioRecord
                                            .getMinBufferSize(16000,
                                                    AudioFormat.CHANNEL_IN_MONO,
                                                    AudioFormat.ENCODING_PCM_16BIT);
                                    record = new AudioRecord(MediaRecorder.AudioSource.MIC,
                                            16000,
                                            AudioFormat.CHANNEL_IN_MONO,
                                            AudioFormat.ENCODING_PCM_16BIT,
                                            recordBufsize);

                                }
                                try {
                                    socket = new Socket("192.168.1.101", 10001);
                                    in = socket.getInputStream();
                                    out = socket.getOutputStream();
                                    Snackbar.make(view, "fay控制器连接成功", Snackbar.LENGTH_SHORT)
                                            .setAction("Action", null).show();
                                    Log.d("fay","fay控制器连接成功");
                                }catch(IOException e){
                                    Log.d("fay","socket连接失败");
                                    return;
                                }
                                byte[] data = new byte[1024];
                                record.startRecording();
                                Snackbar.make(view, "麦克风启动成功", Snackbar.LENGTH_SHORT)
                                        .setAction("Action", null).show();
                                Log.d("fay","麦克风启动成功");
                                try {
                                    Snackbar.make(view, "开始传输音频", Snackbar.LENGTH_SHORT)
                                            .setAction("Action", null).show();
                                    Log.d("fay","开始传输音频");
                                    while (MainActivity.this.running) {
                                        record.read(data, 0, 1024);
                                        if (data.length > 0) {
                                            MainActivity.this.out.write(data);
                                        }
                                    }
                                }catch (Exception e){ //通过异常关闭链接
                                    Log.d("fay","服务端关闭");
                                    Snackbar.make(view, "服务端已经关闭", Snackbar.LENGTH_SHORT)
                                            .setAction("Action", null).show();
                                }finally {
                                    running = false;
                                    record.stop();
                                    record = null;
                                    try {
                                        socket.close();
                                    }catch (Exception e){
                                    }
                                    Snackbar.make(view, "结束", Snackbar.LENGTH_SHORT)
                                            .setAction("Action", null).show();
                                    Log.d("fay","结束");
                                }

                            }
                        }

                    }
                });
                sendThread.start();

                receThread = new Thread(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            while (running) {
                                while (socket != null && !socket.isClosed()) {
                                    byte[] data = new byte[9];
                                    byte[] wavhead = new byte[]{0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};//文件传输开始标记
                                    in.read(data);
                                    if (Arrays.equals(wavhead, data)) {
                                        Log.d("fay", "开始接收音频文件");
                                        String filedata = "";
                                        data = new byte[1024];
                                        while (data != null && data.length > 0) {
                                            in.read(data);
                                            filedata += MainActivity.bytesToHexString(data);
                                            int index = filedata.indexOf("080706050403020100");
                                            if (filedata.length() > 9 && index > 0){//wav文件结束标记
                                                filedata = filedata.substring(0, index).replaceAll("F0F1F2F3F4F5F6F7F8", "");
                                                File wavFile = new File(cacheDir, String.format("sample-%s.wav", new Date().getTime() + ""));
                                                wavFile.createNewFile();
                                                FileOutputStream fos = new FileOutputStream(wavFile);
                                                fos.write(MainActivity.decodeHexBytes(filedata.toCharArray()));
                                                fos.close();
                                                Log.d("fay", "wav文件接收完成:" + wavFile.getAbsolutePath() + "," + filedata.length() / 2);
                                                try{
                                                    MediaPlayer player = new MediaPlayer();
                                                    player.setDataSource(wavFile.getAbsolutePath());
                                                    player.prepare();
                                                    Thread.sleep(800);
                                                    player.start();
                                                    player.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {

                                                        @Override
                                                        public void onCompletion(MediaPlayer mp) {
                                                            // TODO Auto-generated method stub
                                                            mp.release();
                                                        }

                                                    });
                                                    player.setLooping(false);
                                                } catch (IOException e) {
                                                    Log.e("fay", e.toString());
                                                }
                                                break;
                                            }

                                        }
                                        try {
                                            Thread.sleep(1000);
                                        } catch (Exception e) {

                                        }

                                    }
                                }
                                try {
                                    Thread.sleep(1000);
                                } catch (Exception e) {

                                }

                            }
                        } catch (Exception e) {
                            Log.e("fay", e.toString());
                        }finally {

                        }
                    }});
                receThread.start();



            }
        });
    }


    public static String bytesToHexString(byte[] data){
        String result="";
        for (int i = 0; i < data.length; i++) {
            result+=Integer.toHexString((data[i] & 0xFF) | 0x100).toUpperCase().substring(1, 3);
        }
        return result;
    }


    public static byte[] decodeHexBytes(char[] data) {
        int len = data.length;
        if ((len & 0x01) != 0) {
            throw new RuntimeException("未知的字符");
        }
        byte[] out = new byte[len >> 1];
        for (int i = 0, j = 0; j < len; i++) {
            int f = toDigit(data[j], j) << 4;
            j++;
            f = f | toDigit(data[j], j);
            j++;
            out[i] = (byte) (f & 0xFF);
        }
        return out;
    }

    protected static int toDigit(char ch, int index) {
        int digit = Character.digit(ch, 16);
        if (digit == -1) {
            throw new RuntimeException("非法16进制字符 " + ch
                    + " 在索引 " + index);
        }
        return digit;
    }
}