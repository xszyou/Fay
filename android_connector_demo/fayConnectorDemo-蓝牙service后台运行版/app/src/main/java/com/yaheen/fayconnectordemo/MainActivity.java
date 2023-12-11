package com.yaheen.fayconnectordemo;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.Manifest;
import android.app.ActivityManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
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
import java.util.List;

public class MainActivity extends AppCompatActivity {
    private TextView tv = null;
    private boolean running = false;
    private Intent serviceIntent = null;


    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        tv = this.findViewById(R.id.tv);
        serviceIntent = new Intent(this, FayConnectorService.class);

        //按钮点击
        tv.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                Log.d("fay","onclick");
                running = FayConnectorService.running;//isServiceRunning();//同步service的运行状态,不好使！
                if (!running){//运行
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {//开启
                        if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                            if (ActivityCompat.shouldShowRequestPermissionRationale(MainActivity.this, Manifest.permission.RECORD_AUDIO)) {
                                Log.d("fay", "用户彻底拒绝了权限");
                                return;
                            } else {
                                //  用户未彻底拒绝授予权限
                                ActivityCompat.requestPermissions(MainActivity.this, new String[]{Manifest.permission.RECORD_AUDIO}, 1);
                            }
                        }

                        if (ContextCompat.checkSelfPermission(MainActivity.this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                            Log.d("fay","权限ok");

                                Snackbar.make(view, "正在连接fay控制器", Snackbar.LENGTH_SHORT)
                                        .setAction("Action", null).show();
                                startForegroundService(serviceIntent);
                                running = true;
                        }
                    }
                } else{//关闭
                    stopService(serviceIntent);
                    Snackbar.make(view, "已经断开fay控制器", Snackbar.LENGTH_SHORT)
                            .setAction("Action", null).show();
                    running = false;
                }

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

    private boolean isServiceRunning() {
        ActivityManager activityManager = (ActivityManager) this.getApplicationContext()
                .getSystemService(Context.ACTIVITY_SERVICE);
        ComponentName serviceName = new ComponentName("com.yaheen.fayconnectordemo", ".FayConnectorService");
        PendingIntent intent = activityManager.getRunningServiceControlPanel(serviceName);
        if (intent == null){
            return false;
        }
        return true;

    }
}