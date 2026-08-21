# BOSCH 식각 가상계측 - APACHE6 크로스컴파일
#
#   make            : aarch64 (보드용)
#   make native     : x86 (VM에서 검증)
#   make ARCH=a65   : Cortex-A65AE 타깃 최적화 (dotprod/fp16 활성)
#   make clean

CROSS  ?= aarch64-none-linux-gnu-
CC     := $(CROSS)gcc

# 기본은 SDK와 동일한 A53 타깃(비교 기준)
MCPU_a53 := -mcpu=cortex-a53
MCPU_a65 := -march=armv8.2-a+dotprod+fp16 -mtune=cortex-a65
ARCH   ?= a53
MCPU   := $(MCPU_$(ARCH))

CFLAGS  := -O2 -std=gnu99 -Wall -Wextra $(MCPU)
LDFLAGS := -lm

SRC := vm_master.c vm_engine.c
BIN := vm_master

all: $(BIN)

$(BIN): $(SRC) vm_engine.h vm_ipc.h vm_model.h
	$(CC) $(CFLAGS) -o $@ $(SRC) $(LDFLAGS)
	@echo "--- built: $@ ($(ARCH)) ---"
	@file $@ 2>/dev/null || true

# VM에서 자체 검증용 (x86)
native: $(SRC)
	gcc -O2 -std=gnu99 -Wall -Wextra -o vm_master_native $(SRC) -lm
	@echo "--- built: vm_master_native (x86) ---"

# A53 vs A65AE 성능 비교용 2개 동시 빌드
both:
	$(MAKE) ARCH=a53 BIN=vm_master_a53
	$(MAKE) ARCH=a65 BIN=vm_master_a65

clean:
	rm -f vm_master vm_master_a53 vm_master_a65 vm_master_native

.PHONY: all native both clean
