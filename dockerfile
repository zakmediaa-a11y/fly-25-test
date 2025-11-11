FROM alpine:latest
RUN apk add --no-cache nmap
CMD ["sh", "-c", "nmap -p 25 gmail-smtp-in.l.google.com && sleep 9999"]
