package dev.tailnet.chat;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Native shell for Tailnet Chat. The phone connects to a chat node that is
 * already running on the tailnet (e.g. the Raspberry Pi) and shows its UI
 * full-screen. Before connecting it verifies that Tailscale is installed,
 * that a VPN is up, and that the node actually answers.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "tailnet_chat";
    private static final String TAILSCALE_PKG = "com.tailscale.ipn";

    private static final int BG = Color.parseColor("#0e1418");
    private static final int PANEL = Color.parseColor("#232e36");
    private static final int TEXT = Color.parseColor("#e4e9ec");
    private static final int MUTED = Color.parseColor("#8a9aa5");
    private static final int ACCENT = Color.parseColor("#28b487");
    private static final int DANGER = Color.parseColor("#c75450");

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (host().isEmpty()) {
            showSetup();
        } else {
            startChecks();
        }
    }

    // --- Stored node address ---

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private String host() {
        return prefs().getString("host", "");
    }

    private int port() {
        return prefs().getInt("port", 8000);
    }

    private String nodeUrl() {
        return "http://" + host() + ":" + port() + "/";
    }

    // --- Small UI builders (no layout XML needed for this shell) ---

    private int dp(int v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                getResources().getDisplayMetrics()));
    }

    private LinearLayout column() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(22), dp(26), dp(22), dp(26));
        col.setBackgroundColor(BG);
        return col;
    }

    private TextView label(String text, float sp, int color, boolean bold) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        tv.setTextColor(color);
        if (bold) tv.setTypeface(Typeface.DEFAULT_BOLD);
        tv.setPadding(0, dp(6), 0, dp(6));
        return tv;
    }

    private EditText field(String hint, String value, boolean numeric) {
        EditText et = new EditText(this);
        et.setHint(hint);
        et.setText(value);
        et.setTextColor(TEXT);
        et.setHintTextColor(MUTED);
        et.setBackgroundColor(PANEL);
        et.setPadding(dp(14), dp(12), dp(14), dp(12));
        if (numeric) et.setInputType(InputType.TYPE_CLASS_NUMBER);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        et.setLayoutParams(lp);
        return et;
    }

    private Button button(String text, int bgColor, int fgColor, View.OnClickListener onClick) {
        Button b = new Button(this);
        b.setText(text);
        b.setBackgroundColor(bgColor);
        b.setTextColor(fgColor);
        b.setOnClickListener(onClick);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(14);
        b.setLayoutParams(lp);
        return b;
    }

    private void setScreen(LinearLayout col) {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(BG);
        scroll.setFillViewport(true);
        scroll.addView(col);
        setContentView(scroll);
    }

    // --- Screens ---

    private void showSetup() {
        webView = null;
        LinearLayout col = column();
        col.addView(label("Tailnet Chat", 22, TEXT, true));
        col.addView(label("Enter the address of a chat node on your tailnet — e.g. the Raspberry Pi. "
                + "Use its Tailscale IP (100.x.y.z) or MagicDNS hostname.", 14, MUTED, false));

        final EditText hostIn = field("Tailscale IP / hostname", host(), false);
        final EditText portIn = field("Port", String.valueOf(port()), true);
        final TextView error = label("", 13, DANGER, false);

        col.addView(hostIn);
        col.addView(portIn);
        col.addView(button("Connect", ACCENT, Color.parseColor("#06281c"), new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String h = hostIn.getText().toString().trim();
                int p;
                try {
                    p = Integer.parseInt(portIn.getText().toString().trim());
                } catch (NumberFormatException e) {
                    p = -1;
                }
                if (h.isEmpty() || h.contains("/") || h.contains(" ")) {
                    error.setText("Enter a valid IP or hostname (no slashes or spaces).");
                    return;
                }
                if (p < 1 || p > 65535) {
                    error.setText("Port must be between 1 and 65535.");
                    return;
                }
                prefs().edit().putString("host", h).putInt("port", p).apply();
                startChecks();
            }
        }));
        col.addView(error);
        setScreen(col);
    }

    private void startChecks() {
        webView = null;
        LinearLayout col = column();
        ProgressBar pb = new ProgressBar(this);
        col.addView(pb);
        col.addView(label("Checking Tailscale and node " + host() + ":" + port() + "…", 15, MUTED, false));
        setScreen(col);

        new Thread(new Runnable() {
            @Override
            public void run() {
                final boolean installed = isTailscaleInstalled();
                final boolean vpnUp = isVpnActive();
                final String nodeError = checkNode();
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (nodeError == null) {
                            showChat();
                        } else {
                            showError(installed, vpnUp, nodeError);
                        }
                    }
                });
            }
        }).start();
    }

    private void showError(boolean installed, boolean vpnUp, String nodeError) {
        LinearLayout col = column();
        col.addView(label("Can't reach the chat", 20, TEXT, true));

        if (!installed) {
            col.addView(label("✗ The Tailscale app is not installed on this phone.", 14.5f, DANGER, false));
        } else if (!vpnUp) {
            col.addView(label("✗ Tailscale appears to be OFF (no VPN is active). Open Tailscale and connect.",
                    14.5f, DANGER, false));
        } else {
            col.addView(label("✓ Tailscale VPN is active.", 14.5f, ACCENT, false));
        }
        col.addView(label("✗ " + nodeError, 14.5f, DANGER, false));
        col.addView(label("Make sure the node is running on that device and the address under "
                + "\"Change node address\" is its Tailscale IP.", 13.5f, MUTED, false));

        col.addView(button("Retry", ACCENT, Color.parseColor("#06281c"), new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                startChecks();
            }
        }));
        if (!installed) {
            col.addView(button("Get Tailscale", PANEL, TEXT, new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    openTailscaleInstallPage();
                }
            }));
        } else {
            col.addView(button("Open Tailscale", PANEL, TEXT, new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    Intent launch = getPackageManager().getLaunchIntentForPackage(TAILSCALE_PKG);
                    if (launch != null) startActivity(launch);
                }
            }));
        }
        col.addView(button("Change node address", PANEL, TEXT, new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showSetup();
            }
        }));
        setScreen(col);
    }

    private void showChat() {
        webView = new WebView(this);
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        webView.setBackgroundColor(BG);
        webView.setWebViewClient(new WebViewClient());  // keep navigation inside the app
        webView.loadUrl(nodeUrl());
        setContentView(webView);
    }

    // --- Checks ---

    private boolean isTailscaleInstalled() {
        try {
            getPackageManager().getPackageInfo(TAILSCALE_PKG, 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private boolean isVpnActive() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            for (Network n : cm.getAllNetworks()) {
                NetworkCapabilities caps = cm.getNetworkCapabilities(n);
                if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)) {
                    return true;
                }
            }
        } catch (Exception ignored) {
            // treat as unknown; the node reachability check is what really matters
        }
        return false;
    }

    /** Returns null when the node answers, otherwise a human-readable problem. */
    private String checkNode() {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(nodeUrl() + "local/status").openConnection();
            conn.setConnectTimeout(4000);
            conn.setReadTimeout(4000);
            int code = conn.getResponseCode();
            if (code == 200) return null;
            return "Node at " + host() + ":" + port() + " answered with HTTP " + code + ".";
        } catch (IOException e) {
            return "Could not reach " + host() + ":" + port() + " (" + e.getMessage() + ").";
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private void openTailscaleInstallPage() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + TAILSCALE_PKG)));
        } catch (Exception e) {
            startActivity(new Intent(Intent.ACTION_VIEW,
                    Uri.parse("https://play.google.com/store/apps/details?id=" + TAILSCALE_PKG)));
        }
    }

    // --- Menu / navigation ---

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add(0, 1, 0, "Re-run checks");
        menu.add(0, 2, 0, "Change node address");
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == 1) {
            startChecks();
            return true;
        }
        if (item.getItemId() == 2) {
            showSetup();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
