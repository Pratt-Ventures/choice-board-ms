<template>
  <v-dialog :model-value="modelValue" max-width="780" scrollable @update:model-value="emit('update:modelValue', $event)">
    <v-card class="pc-dialog-card">
      <v-card-text class="pa-6">
        <div class="d-flex align-center justify-space-between mb-1">
          <div class="text-h6 font-weight-bold font-display" style="letter-spacing: -.01em">
            Quick start — signed toolkit API
          </div>
          <v-btn icon variant="text" size="small" @click="emit('update:modelValue', false)">
            <i class="fa-solid fa-xmark" />
          </v-btn>
        </div>
        <div class="text-body-2 text-medium-emphasis mb-4">
          Create an application, issue a key set, then call toolkit endpoints with signed headers.
        </div>
        <div class="d-flex flex-wrap ga-2 mb-5">
          <v-chip size="small" variant="tonal" color="primary">
            <v-icon start size="13">mdi-play-circle-outline</v-icon>1 · Create application
          </v-chip>
          <v-chip size="small" variant="tonal" color="primary">
            <v-icon start size="13">mdi-play-circle-outline</v-icon>2 · Issue API key set
          </v-chip>
          <v-chip size="small" variant="tonal" color="primary">
            <v-icon start size="13">mdi-play-circle-outline</v-icon>3 · Call /api/api-check
          </v-chip>
        </div>
        <v-tabs v-model="tab" color="primary" density="compact" class="mb-3">
          <v-tab value="curl">curl</v-tab>
          <v-tab value="python">Python</v-tab>
          <v-tab value="js">Node / JS</v-tab>
        </v-tabs>
        <v-window v-model="tab">
          <v-window-item value="curl">
            <div class="code-block">{{ curlSample }}</div>
          </v-window-item>
          <v-window-item value="python">
            <div class="code-block">{{ pythonSample }}</div>
          </v-window-item>
          <v-window-item value="js">
            <div class="code-block">{{ jsSample }}</div>
          </v-window-item>
        </v-window>
        <div class="text-caption text-medium-emphasis mt-3">
          <v-icon size="13" class="mr-1">mdi-shield-lock-outline</v-icon>
          Payloads are signed with the key's shared secret; the requestor identifier binds the call to your account.
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const tab = ref('curl')

const curlSample = `curl -X POST "https://api.example.com/api/api-check" \\
  -H "api-request-authentication: <requestor-id>" \\
  -H "api-request-signature: <hmac-sha256-of-body>" \\
  -H "content-type: application/json" \\
  -d '{"ping":"pong"}'

# -> true`

const pythonSample = `import hashlib, hmac, json, requests, time

KEY_ID = "<requestor-id>"
SECRET = b"<shared-secret>"
payload = json.dumps({"ping": "pong"}, separators=(",", ":")).encode()
ts = int(time.time())
sig = hmac.new(SECRET, payload, hashlib.sha256).hexdigest()

r = requests.post(
    "https://api.example.com/api/api-check",
    data=payload,
    headers={
        "api-request-authentication": KEY_ID,
        "api-request-signature": f"v1={sig},t={ts}",
        "content-type": "application/json",
    },
    timeout=5,
)
print(r.json())`

const jsSample = `import crypto from "node:crypto";

const KEY_ID = "<requestor-id>";
const payload = JSON.stringify({ ping: "pong" });
const ts = Math.floor(Date.now() / 1000);
const sig = crypto.createHmac("sha256", SHARED_SECRET).update(payload).digest("hex");

const res = await fetch("https://api.example.com/api/api-check", {
  method: "POST",
  headers: {
    "api-request-authentication": KEY_ID,
    "api-request-signature": \`v1=\${sig},t=\${ts}\`,
    "content-type": "application/json",
  },
  body: payload,
});
console.log(await res.json());`
</script>
