	AREA	Init, CODE, READONLY
		CODE32

Start
		mov		r0, #CPSR_Irq
		msr		cpsr_c, r0
		ldr		sp, [pc, #0x30]
		mov		r0, #0
		ldr		r1, [pc, #0x34]
		strh		r0, [r1]
		mov		r0, #CPSR_System
		msr		cpsr_c, r0
		ldr		sp, [pc, #0x1c]
		ldr		r0, [pc, #0x24]
		ldr		r1, [pc, #0x18]
		str		r0, [r1]
		ldr		r0, [pc, #0x1c]
		mov		lr, pc
		bx		r0
		b		Start

		DCD		Sp_Irq
		DCD		Sp_System
		DCD		Irq_Vector
		DCD		Zeroed_Halfword
		DCD		Irq_Handler
		DCD		Thumb_Entry

		mrs		r0, cpsr
		bic		r0, r0, #0x80
		msr		cpsr_c, r0
		bx		lr

		mrs		r0, cpsr
		orr		r0, r0, #0x80
		msr		cpsr_c, r0
		bx		lr

	END
