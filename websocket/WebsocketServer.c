/*
* QBO WebSocket bridge: FIFOs <-> libwebsockets.
* Requires: libwebsockets, pthread.
*
* Note: lws_write() is normally meant to run from the lws service thread; the
* FIFO threads call it with a mutex for compatibility with the original design.
* For strict correctness, consider queueing messages and writing from a callback.
*/

#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>




#include <libwebsockets.h>




#define KGRN "\033[0;32;32m"
#define KCYN "\033[0;36m"
#define KRED "\033[0;32;31m"
#define KYEL "\033[1;33m"
#define KBLU "\033[0;32;34m"
#define KCYN_L "\033[1;36m"
#define RESET "\033[0m"




#define FIFO_READ_CHUNK 1024
#define WS_TX_BUF (LWS_SEND_BUFFER_PRE_PADDING + FIFO_READ_CHUNK + LWS_SEND_BUFFER_POST_PADDING)




static volatile sig_atomic_t destroy_flag;
static struct lws *wsi_p;
static pthread_mutex_t ws_mutex = PTHREAD_MUTEX_INITIALIZER;




static const char *const fifo_say = "/opt/qbo/pipes/pipe_say";
static const char *const fifo_cmd = "/opt/qbo/pipes/pipe_cmd";
static const char *const fifo_listen = "/opt/qbo/pipes/pipe_listen";
static const char *const fifo_feel = "/opt/qbo/pipes/pipe_feel";
static const char *const fifo_findFace = "/opt/qbo/pipes/pipe_findFace";




static void INT_HANDLER(int signo)
{
  (void)signo;
  destroy_flag = 1;
}




/* Write UTF-8 text frame to the active client (if any). */
static int websocket_write_back(struct lws *wsi_in, const char *str, int str_size_in)
{
  if (str == NULL || wsi_in == NULL)
      return -1;




  size_t len = (str_size_in < 1) ? strlen(str) : (size_t)str_size_in;
  char *out = (char *)malloc(WS_TX_BUF);
  if (out == NULL)
      return -1;




  memcpy(out + LWS_SEND_BUFFER_PRE_PADDING, str, len);
  int n = lws_write(wsi_in, (unsigned char *)out + LWS_SEND_BUFFER_PRE_PADDING, len, LWS_WRITE_TEXT);
  printf(KBLU "[websocket_write_back] %s\n" RESET, str);
  free(out);
  return n;
}




static int websocket_broadcast_safe(const char *msg)
{
  int n = -1;




  pthread_mutex_lock(&ws_mutex);
  if (wsi_p != NULL)
      n = websocket_write_back(wsi_p, msg, -1);
  pthread_mutex_unlock(&ws_mutex);
  return n;
}




static void *inspect_PIPE_LISTEN(void *arg)
{
  (void)arg;
  char listen_buff[FIFO_READ_CHUNK];
  char strTextToSend[FIFO_READ_CHUNK + 32];




  for (;;) {
      sleep(1);
      memset(listen_buff, 0, sizeof(listen_buff));




      int fd = open(fifo_listen, O_RDONLY);
      if (fd < 0) {
          perror("open fifo_listen");
          continue;
      }
      ssize_t nread = read(fd, listen_buff, sizeof(listen_buff) - 1);
      close(fd);




      if (nread > 0) {
          listen_buff[nread < (ssize_t)sizeof(listen_buff) ? (size_t)nread : sizeof(listen_buff) - 1] = '\0';
          printf("From FIFO_LISTEN: %s\n", listen_buff);
          snprintf(strTextToSend, sizeof(strTextToSend), "Text: %s", listen_buff);
          websocket_broadcast_safe(strTextToSend);
      }
  }
  return NULL;
}




static void *inspect_PIPE_FEEL(void *arg)
{
  (void)arg;
  char listen_buff[FIFO_READ_CHUNK];




  for (;;) {
      sleep(1);
      memset(listen_buff, 0, sizeof(listen_buff));




      int fd = open(fifo_feel, O_RDONLY);
      if (fd < 0) {
          perror("open fifo_feel");
          continue;
      }
      ssize_t nread = read(fd, listen_buff, sizeof(listen_buff) - 1);
      close(fd);




      if (nread > 0) {
          listen_buff[nread < (ssize_t)sizeof(listen_buff) ? (size_t)nread : sizeof(listen_buff) - 1] = '\0';
          printf("From FIFO_FEEL: %s\n", listen_buff);
          websocket_broadcast_safe(listen_buff);
      }
  }
  return NULL;
}




static void *inspect_PIPE_FIND_FACE(void *arg)
{
  (void)arg;
  char listen_buff[FIFO_READ_CHUNK];
  char strTextToSend[FIFO_READ_CHUNK + 32];




  for (;;) {
      sleep(1);
      memset(listen_buff, 0, sizeof(listen_buff));




      int fd = open(fifo_findFace, O_RDONLY);
      if (fd < 0) {
          perror("open fifo_findFace");
          continue;
      }
      ssize_t nread = read(fd, listen_buff, sizeof(listen_buff) - 1);
      close(fd);




      if (nread > 0) {
          listen_buff[nread < (ssize_t)sizeof(listen_buff) ? (size_t)nread : sizeof(listen_buff) - 1] = '\0';
          printf("From FIFO_FIND_FACE: %s\n", listen_buff);
          snprintf(strTextToSend, sizeof(strTextToSend), "Face: %s", listen_buff);
          websocket_broadcast_safe(strTextToSend);




          fd = open(fifo_findFace, O_RDONLY | O_NONBLOCK);
          if (fd >= 0) {
              (void)read(fd, listen_buff, sizeof(listen_buff));
              close(fd);
          }
      }
  }
  return NULL;
}




struct per_session_data {
  int fd;
};




static int ws_service_callback(struct lws *wsi, enum lws_callback_reasons reason, void *user, void *in, size_t len)
{
  (void)user;




  switch (reason) {
  case LWS_CALLBACK_ESTABLISHED:
      pthread_mutex_lock(&ws_mutex);
      wsi_p = wsi;
      pthread_mutex_unlock(&ws_mutex);
      printf(KYEL "[Main Service] Connection established\n" RESET);
      break;




  case LWS_CALLBACK_RECEIVE: {
      if (in == NULL || len == 0)
          break;




      char in_copy[1024];
      size_t copy_len = len;
      if (copy_len >= sizeof(in_copy))
          copy_len = sizeof(in_copy) - 1;
      memcpy(in_copy, in, copy_len);
      in_copy[copy_len] = '\0';




      printf(KCYN_L "[Main Service] Server received:%s\n" RESET, in_copy);




      /* Same token walk as original: first strtok(NULL) before checking "say". */
      int cmd_say = 0;
      char *saveptr = NULL;
      char *token = strtok_r(in_copy, " ", &saveptr);
      while (token) {
          token = strtok_r(NULL, " ", &saveptr);
          if (token && strcmp(token, "say") == 0) {
              token = strtok_r(NULL, " ", &saveptr);
              if (token && strcmp(token, "-t") == 0) {
                  cmd_say = 1;
                  token = strtok_r(NULL, "\"", &saveptr);
                  if (token) {
                      int fd = open(fifo_say, O_WRONLY);
                      if (fd >= 0) {
                          (void)write(fd, token, strlen(token));
                          close(fd);
                      } else
                          perror("open fifo_say");
                  }
              }
              break;
          }
      }




      char strSystem[256];
      if (!cmd_say) {
          int fd = open(fifo_cmd, O_WRONLY);
          if (fd >= 0) {
              snprintf(strSystem, sizeof(strSystem), "To FIFO_CMD: %s\n", in_copy);
              (void)write(fd, in_copy, strlen(in_copy));
              close(fd);
          } else {
              perror("open fifo_cmd");
              snprintf(strSystem, sizeof(strSystem), "To FIFO_CMD: (open failed)");
          }
      } else {
          snprintf(strSystem, sizeof(strSystem), "To FIFO_SAY: ok\n");
      }




      printf("%s\n", strSystem);
      pthread_mutex_lock(&ws_mutex);
      if (wsi_p != NULL)
          websocket_write_back(wsi, strSystem, -1);
      pthread_mutex_unlock(&ws_mutex);
      break;
  }




  case LWS_CALLBACK_CLOSED:
      pthread_mutex_lock(&ws_mutex);
      if (wsi_p == wsi)
          wsi_p = NULL;
      pthread_mutex_unlock(&ws_mutex);
      printf(KYEL "[Main Service] Client closed.\n" RESET);
      break;




  default:
      break;
  }




  return 0;
}




static struct lws_protocols protocols[] = {
  {
      "my-echo-protocol",
      ws_service_callback,
      sizeof(struct per_session_data),
      4096,
  },
  { NULL, NULL, 0, 0 },
};




int main(void)
{
  const int port = 51717;
  struct lws_context_creation_info info;
  struct lws_context *context;




  struct sigaction act;
  memset(&act, 0, sizeof(act));
  act.sa_handler = INT_HANDLER;
  sigemptyset(&act.sa_mask);
  if (sigaction(SIGINT, &act, NULL) != 0) {
      perror("sigaction");
      return 1;
  }




  memset(&info, 0, sizeof(info));
  info.port = (unsigned int)port;
  info.iface = NULL;
  info.protocols = protocols;
  info.extensions = NULL;
  info.ssl_cert_filepath = NULL;
  info.ssl_private_key_filepath = NULL;
  info.gid = -1;
  info.uid = -1;
  info.options = 0;




  context = lws_create_context(&info);
  if (context == NULL) {
      fprintf(stderr, KRED "[Main] WebSocket context create error.\n" RESET);
      return 1;
  }
  printf(KGRN "[Main] WebSocket context create success (port %d).\n" RESET, port);




  if (mkfifo(fifo_say, 0666) != 0 && errno != EEXIST)
      perror("mkfifo fifo_say");
  if (mkfifo(fifo_cmd, 0666) != 0 && errno != EEXIST)
      perror("mkfifo fifo_cmd");




  pthread_t tid_listen, tid_feel, tid_face;
  int err = pthread_create(&tid_listen, NULL, inspect_PIPE_LISTEN, NULL);
  if (err != 0)
      fprintf(stderr, "pthread_create LISTEN: %s\n", strerror(err));
  else
      printf("Thread PIPE_LISTEN started.\n");




  err = pthread_create(&tid_feel, NULL, inspect_PIPE_FEEL, NULL);
  if (err != 0)
      fprintf(stderr, "pthread_create FEEL: %s\n", strerror(err));
  else
      printf("Thread PIPE_FEEL started.\n");




  err = pthread_create(&tid_face, NULL, inspect_PIPE_FIND_FACE, NULL);
  if (err != 0)
      fprintf(stderr, "pthread_create FIND_FACE: %s\n", strerror(err));
  else
      printf("Thread PIPE_FIND_FACE started.\n");




  while (!destroy_flag)
      lws_service(context, 50);




  lws_context_destroy(context);
  return 0;
}
