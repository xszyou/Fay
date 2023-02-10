package com.yaheen.fayconnectordemo;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.BitmapFactory;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.MediaPlayer;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.ActivityCompat;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;

import com.google.android.material.snackbar.Snackbar;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.util.Arrays;
import java.util.Date;

public class FayConnectorService extends Service {
    private AudioRecord record;
    private int recordBufsize = 0;
    private Socket socket = null;
    private InputStream in = null;
    private OutputStream out = null;
    public static boolean running = false;
    private File cacheDir = null;
    private String channelId = null;
    private  PendingIntent pendingIntent = null;
    private  NotificationManagerCompat notificationManager = null;
    private  long totalrece = 0;
    private long totalsend = 0;
    private AudioManager mAudioManager = null;
    private  boolean isPlay = false;


    //创建通知
    private String createNotificationChannel(String channelID, String channelNAME, int level) {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            NotificationChannel channel = new NotificationChannel(channelID, channelNAME, level);
            manager.createNotificationChannel(channel);
            return channelID;
        } else {
            return null;
        }
    }


    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        super.onStartCommand(intent, START_FLAG_REDELIVERY, startId);
        return Service.START_STICKY;

    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d("fay", "服务启动");



        //开启蓝牙传输
        mAudioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        mAudioManager.startBluetoothSco();
        IntentFilter intentFilter = new IntentFilter();
        intentFilter.addAction(AudioManager.ACTION_SCO_AUDIO_STATE_UPDATED);
        BroadcastReceiver receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                int state = intent.getIntExtra(AudioManager.EXTRA_SCO_AUDIO_STATE, -1);
                if (AudioManager.SCO_AUDIO_STATE_CONNECTED == state) {
                    Log.d("fay", "蓝牙sco连接成功");


                }
            }
        };
        this.registerReceiver(receiver, intentFilter);

        running = true;
        this.cacheDir = getApplicationContext().getFilesDir();//getCacheDir();
        Thread sendThread = new Thread(new Runnable() {
            @Override
            public void run() {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    if (ContextCompat.checkSelfPermission(FayConnectorService.this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        if (record == null) {
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
                            Log.d("fay", "fay控制器连接成功");
                        } catch (IOException e) {
                            Log.d("fay", "socket连接失败");
                            running = false;
                            return;
                        }
                        byte[] data = new byte[1024];
                        record.startRecording();
                        Log.d("fay", "麦克风启动成功");
                        try {
                            Log.d("fay", "开始传输音频");
                            while (running) {
                                if (isPlay){
                                    continue;
                                }
                                int size = record.read(data, 0, 1024);
                                if (size > 0) {
                                    out.write(data);
                                    totalsend += data.length / 1024;
                                }else{//录音异常，等待60秒重新录取
                                    try {
                                        Thread.sleep(60000);
                                        record.stop();
                                        record.startRecording();
                                    }catch (Exception e){
                                    }
                                }
                            }
                        } catch (Exception e) { //通过异常关退出循环
                            Log.d("fay", "服务端关闭：" + e.toString());
                        } finally {
                            running = false;
                            record.stop();
                            record = null;
                            ((AudioManager) getSystemService(Context.AUDIO_SERVICE)).stopBluetoothSco();
                            try {
                                socket.close();
                            } catch (Exception e) {
                            }
                            socket = null;
                            Log.d("fay", "send线程结束");

                        }

                    }
                }

            }
        });


        Thread receThread = new Thread(new Runnable() {
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
                                int len = 0;
                                while ((len = in.read(data)) != -1) {
                                    byte[] temp = new byte[len];
                                    System.arraycopy(data, 0, temp, 0, len);
                                    filedata += MainActivity.bytesToHexString(temp);
                                    int index = filedata.indexOf("080706050403020100");
                                    if (filedata.length() > 9 && index > 0) {//wav文件结束标记
                                        filedata = filedata.substring(0, index).replaceAll("F0F1F2F3F4F5F6F7F8", "");
                                        File wavFile = new File(cacheDir, String.format("sample-%s.wav", new Date().getTime() + ""));
                                        wavFile.createNewFile();
                                        FileOutputStream fos = new FileOutputStream(wavFile);
                                        fos.write(MainActivity.decodeHexBytes(filedata.toCharArray()));
                                        fos.close();
                                        totalrece += filedata.length() / 2 / 1024;
                                        Log.d("fay", "wav文件接收完成:" + wavFile.getAbsolutePath() + "," + filedata.length() / 2);
                                        try {
                                            MediaPlayer player = new MediaPlayer();
                                            player.setDataSource(wavFile.getAbsolutePath());
                                            player.setOnPreparedListener(new MediaPlayer.OnPreparedListener() {
                                                @Override
                                                public void onPrepared(MediaPlayer mp) {
                                                    Log.d("fay", "开始播放");
                                                    if (mAudioManager.isBluetoothScoOn()){
                                                        mAudioManager.stopBluetoothSco();
                                                        mAudioManager.setBluetoothScoOn(false);
                                                        mAudioManager.setMode(mAudioManager.MODE_NORMAL);
                                                    }
                                                    try {
                                                        Thread.sleep(500);
                                                    }catch (Exception e){

                                                    }
                                                    isPlay = true;
                                                    mp.start();
                                                }
                                            });
                                            player.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {

                                                @Override
                                                public void onCompletion(MediaPlayer mp) {
                                                    Log.d("fay", "播放完成");
                                                    isPlay = false;
                                                    mp.release();
                                                    mAudioManager.startBluetoothSco();
                                                    mAudioManager.setMode(mAudioManager.MODE_IN_CALL);
                                                    mAudioManager.setBluetoothScoOn(true);


                                                }

                                            });
                                            player.setVolume(1,1);
                                            player.setLooping(false);
                                            player.prepareAsync();

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
                } catch (Exception e) {//通过异常判断socket已经关闭，退出循环

                } finally {
                    Log.d("fay", "rece线程结束");

                }
            }
        });
        sendThread.start();
        receThread.start();

        //通知栏
        new Thread(new Runnable() {
            @Override
            public void run() {
                try{
                    while (running) {
                        Thread.sleep(3000);
                        if (totalsend + totalrece > 2048){
                            inotify("fay connector demo", "已经连接fay控制器，累计接收/发送：" + String.format("%.2f", (double)totalrece / 1024) + "/" + String.format("%.2f", (double)totalsend / 1024) + "MB");
                        } else {
                            inotify("fay connector demo", "已经连接fay控制器，累计接收/发送：" + totalrece + "/" + totalsend + "KB");
                        }
                    }
                    inotify("fay connector demo", "已经断开fay控制器");
                }catch (Exception e){
                    Log.e("fay", e.toString());
                }finally {
                    FayConnectorService.this.stopSelf();
                }
            }
        }).start();


    }

    private void inotify(String title, String content){
        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        if (pendingIntent == null){
            pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE);
        }
        if (channelId == null){
            channelId = createNotificationChannel("my_channel_ID", "my_channel_NAME", NotificationManager.IMPORTANCE_HIGH);
        }
        if (notificationManager == null){
            notificationManager = NotificationManagerCompat.from(this);
        }
        NotificationCompat.Builder notification2 = new NotificationCompat.Builder(FayConnectorService.this, channelId)
                .setContentTitle(title)
                .setContentText(content)
                .setContentIntent(pendingIntent)
                .setSmallIcon(R.drawable.icon)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true);
        //notificationManager.notify(100, notification2.build());
        startForeground(100, notification2.build());
    }




    @Override
    public void onDestroy() {
        Log.d("fay", "服务关闭");
        super.onDestroy();
        mAudioManager.stopBluetoothSco();
        running = false;
        stopForeground(true);
    }
}
