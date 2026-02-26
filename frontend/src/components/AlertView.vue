<template>
  <div class="alert-view">
    <AlertList />
  </div>
</template>

<script setup lang="ts">
import AlertList from './AlertList.vue'
</script>

<style scoped>
.alert-view {
  height: 100%;
  padding: 16px;
  overflow: hidden;
}
</style>
