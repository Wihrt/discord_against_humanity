{{/*
Expand the name of the chart.
*/}}
{{- define "discord-against-humanity.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "discord-against-humanity.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "discord-against-humanity.labels" -}}
helm.sh/chart: {{ include "discord-against-humanity.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "discord-against-humanity.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "discord-against-humanity.selectorLabels" -}}
app.kubernetes.io/name: {{ include "discord-against-humanity.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "discord-against-humanity.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "discord-against-humanity.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the secret holding the Discord token.
*/}}
{{- define "discord-against-humanity.secretName" -}}
{{- if .Values.existingSecret }}
{{- .Values.existingSecret }}
{{- else }}
{{- include "discord-against-humanity.fullname" . }}
{{- end }}
{{- end }}
