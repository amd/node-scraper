#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[])
{
    int i;

    printf("CCompileRunPlugin: OK\n");

    for (i = 1; i < argc; i++) {
        printf("arg[%d]=%s\n", i, argv[i]);
    }

    return 0;
}
